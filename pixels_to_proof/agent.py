"""The audit agent: paper + supplementary files in, a verdict or a reasoned refusal per claim out.

Muse Spark proposes (file roles, column meanings, claims, frame reads, re-proposals after a rejection); code checks
every proposal against the files and the physics; SAM 3.1 tracks. Every step is written to the run ledger."""
from __future__ import annotations

import json
import math
import re
import time
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

from . import (ingest, measure, meta, pairing, pipeline, plan as planmod, read, receipt, scale, shots, tablecheck, track,
               verdict)
from .ledger import Ledger

ROOT = Path(__file__).resolve().parent.parent
CHECKS = ROOT / "checks.toml"
SCRIPT_EXT = {".r", ".py", ".m", ".jl", ".ipynb", ".txt"}


def thresholds() -> dict:
    return tomllib.loads(CHECKS.read_text())


@dataclass
class Unit:
    """One measurable piece of video: a shot, or one panel of a montage shot."""
    video: str
    shot: int                 # 1-based shot index in the video
    first: int
    last: int
    crop: tuple[int, int, int, int] | None = None
    panel: int | None = None
    label: str = ""
    rec: int | None = None    # 1-based recording within a shot that Muse Spark split (checked by code)

    @property
    def uid(self) -> str:
        stem = str(Path(self.video).with_suffix("")).replace("/", "_").replace("\\", "_")
        return (f"{stem}_s{self.shot}" + (f"r{self.rec}" if self.rec is not None else "")
                + (f"_p{self.panel}" if self.panel is not None else ""))


def _timed(fn):
    t = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t


def ingest_stage(bundle: Path, out: Path, led: Ledger) -> dict:
    inv = ingest.inventory(bundle)
    led.step("inventory", f"{len(inv.pdfs)} pdf, {len(inv.videos)} video, {len(inv.tables)} table, "
                          f"{len(inv.archives)} archive files")
    if not inv.pdfs:
        raise ValueError("no PDF in the bundle")
    # The paper: the PDF that states a licence (supplements usually do not); among those, the longest text.
    texts = {p: ingest.pdf_text(bundle / p) for p in inv.pdfs}
    ranked = sorted(inv.pdfs, key=lambda p: (ingest.licence(texts[p])[0] is not None, len(texts[p])))
    pdf, text = bundle / ranked[-1], texts[ranked[-1]]
    lic, snippet = ingest.licence(text)
    led.step("paper", f"{ranked[-1]} chosen as the paper" + (f" (of {len(inv.pdfs)} PDFs)" if len(inv.pdfs) > 1 else ""))
    led.gate("G0 licence", lic is not None, f"{lic}: {snippet[:160]}" if lic else snippet)
    tables = [t for f in inv.tables for t in ingest.read_tables(bundle / f)]
    scripts = []
    for a in inv.archives:
        for p in ingest.unzip(bundle / a, out / "unzipped" / Path(a).stem):
            if p.suffix.lower() in SCRIPT_EXT and p.stat().st_size < 200_000:
                scripts.append((str(p.relative_to(out / "unzipped")), p.read_text(errors="replace")))
    for f in inv.other:
        p = bundle / f
        if p.suffix.lower() in SCRIPT_EXT and p.stat().st_size < 200_000:
            scripts.append((f, p.read_text(errors="replace")))
    led.step("read files", f"{len(text)} chars of PDF text, {len(tables)} table sheets, {len(scripts)} scripts")
    return {"inventory": inv, "pdf": pdf, "pdf_text": text, "licence": lic, "tables": tables, "scripts": scripts}


def video_units(video: Path, min_frames: int, rel: str | None = None) -> list[Unit]:
    ranges, _ = shots.ranges(video)
    units = []
    for a, b in ranges:             # cut detection also fires inside fades; only real recordings are numbered
        if b - a + 1 >= min_frames:
            units.append(Unit(video=rel or video.name, shot=len(units) + 1, first=a, last=b))
    return units


def check_split(proposal: list[dict], first: int, last: int, sampled: list[int], min_frames: int) -> tuple[list, str]:
    """Gate on Muse Spark's split of one shot into recordings. Returns ([(first, last), ...], reason); an empty list
    means the proposal is rejected and the shot stays whole. A single recording keeps the shot as it is. Spark places
    boundaries only to the nearest tile and tends to widen the transition it sees, so each inner boundary is put in the
    middle of the gap between two proposed recordings and the recordings meet there: a few blended frames may remain at
    the ends, and a flight that a boundary cuts is refused later (G5: the shot ends before the flight does)."""
    recs = sorted((int(r["first_frame"]), int(r["last_frame"])) for r in proposal)
    if not recs:
        return [], "no recording proposed; the shot is kept as it is"
    if len(recs) == 1:
        return [(first, last)], "one recording: the shot is kept as it is"
    step = max(int(np.median(np.diff(sampled))) if len(sampled) > 1 else 1, 1)
    for (a, b), nxt in zip(recs, recs[1:] + [None]):
        if not first - step <= a <= b <= last + step:
            return [], f"recording {a}-{b} is outside the shot {first}-{last}"
        if nxt and b >= nxt[0]:
            return [], f"recordings {a}-{b} and {nxt[0]}-{nxt[1]} overlap"
    cuts = [(b + nxt_a + 1) // 2 for (_, b), (nxt_a, _) in zip(recs, recs[1:])]
    out = list(zip([first] + cuts, [c - 1 for c in cuts] + [last]))
    for (a, b), r in zip(out, recs):
        if b - a + 1 < min_frames:
            return [], f"recording {r[0]}-{r[1]} is shorter than {min_frames} frames"
    return out, f"{len(out)} recordings: " + ", ".join(f"{a}-{b}" for a, b in out) + \
        " (boundaries in the middle of each proposed transition)"


def split_stage(path: Path, rel: str, units: list[Unit], out: Path, led: Ledger, min_frames: int) -> list[Unit]:
    """Muse Spark looks at a contact sheet of every long shot and proposes the separate recordings in it (code-level
    cut detection cannot see a dissolve between two near-identical scenes); code checks each proposal."""
    long_ = [u for u in units if u.last - u.first + 1 >= 3 * min_frames]
    if not long_:
        return units
    vdir = out / "videos" / str(Path(rel).with_suffix("")).replace("/", "_").replace("\\", "_")
    vdir.mkdir(parents=True, exist_ok=True)
    sheets, sampled = [], {}
    for u in long_:
        png = vdir / f"sheet_s{u.shot}.jpg"
        meta_f = vdir / f"sheet_s{u.shot}.json"
        if not png.exists() or not meta_f.exists():
            meta_f.write_text(json.dumps(shots.contact_sheet(path, u.first, u.last, png)))
        sheets.append(png)
        sampled[u.shot] = json.loads(meta_f.read_text())
    cache = vdir / "split.json"
    cached = cache.exists()
    if cached:
        ans, usage, secs = *json.loads(cache.read_text()), 0.0
    else:
        (ans, usage), secs = _timed(lambda: read.split_shots(sheets, rel, [(u.first, u.last) for u in long_]))
        cache.write_text(json.dumps([ans, usage]))
    by_sheet = {int(s_["sheet"]): s_ for s_ in ans["shots"]}
    call = led.model("split shots", meta.SPARK, usage, secs,
                     f"{rel}: " + "; ".join(f"shot {u.shot}: {len(by_sheet.get(i + 1, {}).get('recordings', []))} "
                                            "recording(s)" for i, u in enumerate(long_)), ref=rel, cached=cached)
    result = []
    for u in units:
        if u not in long_:
            result.append(u)
            continue
        prop = by_sheet.get(long_.index(u) + 1)
        recs, why = check_split(prop["recordings"] if prop else [], u.first, u.last, sampled[u.shot], min_frames)
        led.gate("G2 recordings", bool(recs), f"shot {u.shot} ({u.first}-{u.last}): {why}"
                 + (f"; Spark: {prop['evidence'][:120]}" if prop else ""), ref=rel, on=call)
        if prop is not None and not prop["recordings"]:
            result.append(Unit(video=u.video, shot=u.shot, first=u.first, last=u.last, label="no recording proposed"))
        elif len(recs) <= 1:
            result.append(u)
        else:
            result += [Unit(video=u.video, shot=u.shot, first=a, last=b, rec=k + 1) for k, (a, b) in enumerate(recs)]
    return result


def video_stage(bundle: Path, ing: dict, out: Path, led: Ledger) -> list[dict]:
    """Shots (and montage panels) of every video, with Spark's reading of a frame of each (calls run in parallel)."""
    from concurrent.futures import ThreadPoolExecutor
    th = thresholds()
    todo = []
    for v in ing["inventory"].videos:
        path = bundle / v
        units = video_units(path, th["video"]["min_shot_frames"], rel=v)
        led.step("shots", f"{v}: {len(units)} shots of >= {th['video']['min_shot_frames']} frames (cuts and fades)",
                 ref=v)
        units = split_stage(path, v, units, out, led, th["video"]["min_shot_frames"])
        for u in units:
            udir = out / "units" / u.uid
            udir.mkdir(parents=True, exist_ok=True)
            f0, ft = udir / "frame0.png", udir / "frame_text.png"
            if not f0.exists():
                shots.frame_at(path, u.first, f0)
            if not ft.exists():     # overlay text is often typed in after the first frame
                shots.frame_at(path, u.first + int(0.4 * (u.last - u.first)), ft)
            todo.append((u, udir, f0))

    def readone(item):
        u, udir, f0 = item
        cache = udir / "frame_reading.json"
        if cache.exists():
            fr, usage = json.loads(cache.read_text())
            return fr, usage, 0.0, True
        h, w = cv2.imread(str(f0)).shape[:2]
        (fr, usage), secs = _timed(lambda: read.read_frame(f0, w, h, udir / "frame_text.png"))
        cache.write_text(json.dumps([fr, usage]))
        return fr, usage, secs, False

    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(readone, todo))
    rows = []
    for (u, udir, f0), (fr, usage, secs, cached) in zip(todo, results):
        panels = shots.framed_panels(cv2.imread(str(f0)))
        if len(panels) >= 2:
            led.step("montage", f"{u.uid}: {len(panels)} framed panels", ref=u.uid)
        led.model("read frame", meta.SPARK, usage, secs,
                  f"printed text '{' / '.join(fr['overlay_text'].splitlines())[:90]}', fps {fr['capture_fps']}, "
                  f"scale reference {fr['reference_kind']}, object box {fr.get('object_box')}", ref=u.uid,
                  cached=cached)
        rows.append({"unit": asdict(u), "uid": u.uid, "frame_reading": fr, "panels": panels,
                     "n_frames": u.last - u.first + 1})
    return rows


def plan_stage(ing: dict, units: list[dict], out: Path, led: Ledger) -> planmod.CheckedPlan:
    inv = ing["inventory"]
    inv_text = "\n".join([f"pdf: {p}" for p in inv.pdfs] + [f"video: {p}" for p in inv.videos] +
                         [f"table: {p}" for p in inv.tables] + [f"archive: {p}" for p in inv.archives] +
                         [f"script (from archive or folder): {name}" for name, _ in ing["scripts"]])
    tables_text = "\n\n".join(ingest.table_digest(t) for t in ing["tables"])
    scripts_text = "\n\n".join(f"--- {name} ---\n{src[:30000]}" for name, src in ing["scripts"])
    videos_text = "\n".join(
        f"{u['unit']['video']} shot {u['unit']['shot']}"
        + (f" recording {u['unit']['rec']}" if u['unit'].get('rec') else "")
        + f" frames {u['unit']['first']}-{u['unit']['last']}"
        f" ({u['n_frames']} frames): printed text '{u['frame_reading']['overlay_text']}'"
        + (f"; montage with {len(u['panels'])} framed panels" if len(u['panels']) >= 2 else "")
        for u in units)
    overlay = "\n".join(u["frame_reading"]["overlay_text"] for u in units)
    scripts = "\n".join(s for _, s in ing["scripts"])
    feedback, fid, best = "", None, None
    for version in range(1, thresholds()["plan"]["max_reproposals"] + 2):
        cache = out / ("plan_raw.json" if version == 1 else f"plan_raw_v{version}.json")
        cached = cache.exists()
        if cached:
            raw, usage, secs = *json.loads(cache.read_text()), 0.0
        else:
            (res), secs = _timed(lambda: planmod.make_plan(ing["pdf"], inv_text, tables_text, scripts_text,
                                                            videos_text, feedback, fid))
            raw, usage, fid = res
            cache.write_text(json.dumps([raw, usage], ensure_ascii=False))
        call = led.model("plan" if version == 1 else "re-propose plan", meta.SPARK, usage, secs,
                         f"v{version}: {len(raw['claims'])} claims, event table "
                         f"{(raw['event_table'] or {}).get('sheet')}, {len(raw['videos'])} videos, "
                         f"authors' method {raw['authors_speed_method']['family']}", cached=cached)
        if best is not None:              # keep what already passed; take only the re-proposed fields
            raw = planmod.merge(best[1].plan, raw, [c for c in best[1].checks if not c.ok])
        cp = planmod.check(raw, ing["pdf_text"], scripts, ing["tables"], overlay)
        for c in cp.checks:
            if version == 1 or not c.ok or any(k in c.field for k in planmod.CRITICAL):
                led.gate("G1 plan", c.ok, f"v{version} {c.field}: {c.note}", on=call)
        score = len(planmod.feedback_for(cp).splitlines())
        if best is None or score < best[0]:
            best = (score, cp, version)
        feedback = planmod.feedback_for(cp)
        if not feedback:
            break
    score, cp, version = best
    led.step("plan accepted", f"v{version} ({score} needed fields still rejected)")
    planmod.save(cp, out / "plan_checked.json")
    return cp


# ---------------------------------------------------------------------------------------------------------------------
# Video route: per shot/panel inputs -> feasibility -> track -> self-checks -> blind pairing -> verdict
# ---------------------------------------------------------------------------------------------------------------------

_RATE = re.compile(r"(\d[\d,]*\.?\d*)\s*(?:frames?\s*(?:/|per)\s*s(?:ec(?:ond)?)?|fps|frames?\s*s-1)", re.I)


def _overlay_fps(fr: dict) -> tuple[float | None, str]:
    """Spark's fps reading is kept only if the number is printed in the overlay text it transcribed. Otherwise code
    parses the transcribed text itself: the one rate on a line that says captured/recorded/filmed."""
    text = fr.get("overlay_text", "")
    printed = [float(x) for x in re.findall(r"\d[\d,]*\.?\d*", text.replace(",", ""))]
    fps = fr.get("capture_fps")
    if fps and any(abs(p - fps) < 1e-6 for p in printed):
        return float(fps), "printed on the video (read by Spark, number found in the overlay text)"
    rates = []
    for line in text.splitlines():
        if re.search(r"captur|record|film|acquir", line, re.I):
            rates += [float(m.group(1).replace(",", "")) for m in _RATE.finditer(line)]
    if len(set(rates)) == 1:
        return rates[0], ("parsed by code from the overlay text" +
                          (f" (Spark's number {fps:g} is not printed there)" if fps else ""))
    return None, ""


_SPEEDUP = re.compile(r"play\s*-?\s*back[^\n]{0,20}?(\d+(?:\.\d+)?)\s*(?:x|×|times)\s*(faster|slower)", re.I)


def _frame_step(fr: dict) -> tuple[int | None, str]:
    """Camera frames per video frame. A statement 'playback N x faster' on the video means the editor kept every N-th
    camera frame (a frame-by-frame copy plays N times slower than that); 'playback - 30 frames/second' or no statement
    means every camera frame is shown. 'N x slower' or a non-integer factor is ambiguous and refuses the shot. The
    gravity self-check tests the reading independently: a wrong step scales the fitted g by step^2."""
    found = {(float(m.group(1)), m.group(2).lower()) for m in _SPEEDUP.finditer(fr.get("overlay_text", ""))}
    if not found:
        return 1, "every camera frame shown (no speed-up stated on the video)"
    if len(found) > 1:
        return None, f"several playback speeds stated on the video: {sorted(found)}"
    n, kind = found.pop()
    if kind != "faster" or n != int(n) or n < 1:
        return None, f"'playback {n:g}x {kind}' does not say how many camera frames a video frame stands for"
    return int(n), f"'playback {int(n)}x faster' printed on the video: every {int(n)}th camera frame is shown"


def _airborne_range(cp: planmod.CheckedPlan, table) -> tuple[float, float] | None:
    for c in cp.columns.values():
        if c["quantity"] == "airborne_time" and c.get("si_factor"):
            v = [r[c["index"]] * c["si_factor"] for r in table.rows if isinstance(r[c["index"]], (int, float))]
            if v:
                return min(v), max(v)
    return None


def _clip(bundle: Path, u: dict, out: Path) -> Path:
    clip = out / "units" / u["uid"] / "clip.mp4"
    if not clip.exists():
        un = u["unit"]
        shots.extract_region(bundle / un["video"], un["first"], un["last"], clip,
                             tuple(un["crop"]) if un.get("crop") else None)
    return clip


def _gap_inputs(bundle: Path, u: dict, sr: dict, fps: float, src: str, out: Path, led: Ledger) -> dict:
    """Scale from the gap between a take-off platform and a landing platform or vertical target whose separation the
    paper (or the video) states. Both are located by code on the median frame of the shot, where the animal is gone."""
    uid = u["uid"]
    try:
        gap = scale.platform_gap(shots.median_frame(_clip(bundle, u, out)))
    except ValueError as exc:
        led.gate("G4 scale", False, f"no measurable platform gap on this shot ({exc})", ref=uid)
        return {"ok": False, "reason": f"no measurable platform gap on this shot ({exc})"}
    pipeline._gap_evidence(out / "units" / uid / "frame0.png", gap, out / "units" / uid / "scale_evidence.png")
    led.gate("G4 scale", True, f"gap from the platform tip at x={gap.left_tip_px:.0f} px to the {gap.right_kind} at "
                               f"x={gap.right_tip_px:.1f} px = {gap.gap_px:.0f} px = {sr['size_mm']:g} mm "
                               f"(stated: '{sr.get('evidence', '')[:80]}')", ref=uid)
    return {"ok": True, "fps": fps, "fps_source": src, "mm_per_px": gap.mm_per_px(float(sr["size_mm"])),
            "scale_rel_unc": gap.rel_uncertainty(), "gap_px": gap.gap_px, "band": None}


def unit_inputs(u: dict, cp: planmod.CheckedPlan, table, out: Path, led: Ledger, bundle: Path) -> dict:
    """Frame rate and scale for one shot, checked before any tracking. Returns {'ok': False, 'reason'} or inputs."""
    th = thresholds()
    uid, fr = u["uid"], u["frame_reading"]
    fps, src = _overlay_fps(fr)
    if fr.get("capture_fps") and fps != fr.get("capture_fps"):
        led.gate("G4 frame rate", False, f"Spark read {fr['capture_fps']:g} fps but that number is not printed on the "
                                         "shot", ref=uid)
    if fps is None:
        per_file = {v["capture_fps"] for v in cp.plan["videos"]
                    if Path(v["file"]).name == Path(u["unit"]["video"]).name and v["capture_fps"]}
        if len(per_file) == 1:
            fps, src = float(per_file.pop()), "stated in the paper for this video file"
        elif len(per_file) > 1:
            led.gate("G4 frame rate", False, f"the paper gives several rates for this file ({sorted(per_file)}) and "
                                             "none is printed on this shot", ref=uid)
            return {"ok": False, "reason": "frame rate ambiguous for this shot"}
    if fps is None:
        led.gate("G4 frame rate", False, "no frame rate printed on the shot or stated for the file", ref=uid)
        return {"ok": False, "reason": "no frame rate"}
    step, step_note = _frame_step(fr)
    if step is None:
        led.gate("G4 frame rate", False, step_note, ref=uid)
        return {"ok": False, "reason": "playback speed of the shot is ambiguous"}
    if step != 1:
        src += f"; {step_note}, so one video frame = {step}/{fps:g} s"
        fps = fps / step
    led.gate("G4 frame rate", True, f"{fps:g} video frames per second of real time, {src}", ref=uid)
    n = u["n_frames"]
    rng = _airborne_range(cp, table) if table is not None else None
    if rng:
        covered = n / fps
        if covered < rng[0]:
            led.gate("G4 feasibility", False, f"the shot covers {covered * 1000:.1f} ms; the shortest airborne time in "
                                              f"the table is {rng[0] * 1000:.0f} ms, so no whole flight is in it", ref=uid)
            return {"ok": False, "reason": f"shot covers {covered * 1000:.1f} ms, shorter than any flight in the table"}
        if rng[1] * fps < th["selfcheck"]["min_flight_frames"]:
            led.gate("G4 feasibility", False, f"at {fps:g} fps the longest flight in the table spans "
                                              f"{rng[1] * fps:.1f} frames (< {th['selfcheck']['min_flight_frames']})", ref=uid)
            return {"ok": False, "reason": f"at {fps:g} fps a flight spans at most {rng[1] * fps:.1f} frames"}
    sr = cp.plan.get("scale_reference", {})
    kind = fr.get("reference_kind")
    if sr.get("kind") == "platform_gap" and sr.get("size_mm"):
        return _gap_inputs(bundle, u, sr, fps, src, out, led)
    if sr.get("kind") != "grid" or not sr.get("size_mm"):
        led.gate("G4 scale", False, f"the paper states no grid of known size (plan: {sr.get('kind')} "
                                    f"{sr.get('size_mm')} mm)", ref=uid)
        return {"ok": False, "reason": "no scale reference of known size stated in the paper"}
    gray = cv2.imread(str(out / "units" / uid / "frame0.png"), cv2.IMREAD_GRAYSCALE)
    h = gray.shape[0]
    band = fr.get("grid_band_rows") or None
    if band is not None and (len(band) != 2 or band[1] - band[0] < 50 or kind != "grid"):
        band = None
    try:
        grid = scale.grid_from_frame(gray, axis="x", band=tuple(band or (0, h)))
    except ValueError as exc:
        led.gate("G4 scale", False, f"no measurable grid on this shot (Spark saw: {kind}; code: {exc})", ref=uid)
        return {"ok": False, "reason": f"no measurable grid on this shot (seen: {kind})"}
    if kind != "grid":
        # Spark did not report a grid; code accepts one only if it is unmistakable.
        regular = len(grid.lines_px) >= 4 and grid.spacing_sd_px / grid.spacing_px < 0.02
        led.gate("G4 scale", regular, f"Spark reported '{kind}', code found {len(grid.lines_px)} lines at "
                                      f"{grid.spacing_px:.1f} px (sd {grid.spacing_sd_px:.2f})"
                                      + ("; regular enough to use" if regular else "; not regular enough"), ref=uid)
        if not regular:
            return {"ok": False, "reason": f"no measurable grid on this shot (seen: {kind})"}
    est = fr.get("grid_square_px_estimate")
    pipeline._scale_evidence(out / "units" / uid / "frame0.png", grid, tuple(band or (0, h)), fr.get("object_box"),
                             out / "units" / uid / "scale_evidence.png")
    led.gate("G4 scale", True, f"grid {grid.spacing_px:.1f} px (sd {grid.spacing_sd_px:.2f}, {len(grid.lines_px)} lines) "
                               f"= {sr['size_mm']} mm" + (f"; Spark's estimate {est} px" if est else ""), ref=uid)
    return {"ok": True, "fps": fps, "fps_source": src, "mm_per_px": grid.mm_per_px(float(sr["size_mm"])),
            "scale_rel_unc": grid.rel_uncertainty(), "grid_px": grid.spacing_px, "band": band}


def measure_unit(bundle: Path, u: dict, inputs: dict, phrase: str, out: Path, led: Ledger) -> dict:
    th = thresholds()
    uid = u["uid"]
    udir = out / "units" / uid
    clip = _clip(bundle, u, out)
    boxes = [u["frame_reading"].get("object_box")]
    img = cv2.imread(str(udir / "frame0.png"))
    h, w = img.shape[:2]

    def repropose(attempts):
        reason = attempts[-1]["reason"]
        cache = udir / f"rebox_{len(boxes)}.json"
        cached = cache.exists()
        if cached:
            ans, usage, secs = *json.loads(cache.read_text()), 0.0
        else:
            (ans, usage), secs = _timed(lambda: read.repropose_box(udir / "frame0.png", w, h, phrase, reason, boxes))
            cache.write_text(json.dumps([ans, usage]))
        i = led.model("re-propose box", meta.SPARK, usage, secs,
                      f"new box {ans['object_box']} ({ans['what_is_in_the_box'][:60]}); "
                      f"diagnosis: {ans['why_the_previous_failed'][:80]}", ref=uid, cached=cached)
        if len(ans["object_box"]) != 4 or ans["object_box"] in boxes:
            led.gate("G5 track", False, "re-proposed box is invalid or repeats a rejected one", ref=uid, on=i)
            return None
        boxes.append(ans["object_box"])
        return (f"box re-proposed by Muse Spark (round {len(boxes) - 1})", track.box_prompt(ans["object_box"], (w, h)))

    (tm), secs = _timed(lambda: pipeline.track_and_measure(
        clip, u["frame_reading"], phrase, inputs["fps"], inputs["mm_per_px"], udir, repropose=repropose,
        max_reproposals=th["plan"]["max_reproposals"],
        quality_kw={"max_area_jump": th["track"]["max_area_jump"],
                    "min_travel_body_sizes": th["track"]["min_travel_body_sizes"]}))
    for a in tm["attempts"]:
        i = led.model("track", meta.SAM, None, a.get("seconds", 0.0), f"{a['prompt']}: "
                      + (f"{a['quality'].get('frames', 0)} frames tracked" if a.get("quality") else "no track"), ref=uid,
                      cached=a.get("cached", False))
        led.gate("G5 track", a["accepted"], f"{a['prompt']}: " + ("accepted" if a["accepted"] else a["reason"]),
                 ref=uid, on=i)
    if tm["pts"] is None:
        return {"ok": False, "reason": "no usable track: " + "; ".join(a["reason"] for a in tm["attempts"])}
    k = tm["k"]
    if k.truncated:
        led.gate("G5 track", False, f"the flight is still under way at the last frame of the shot (frame {k.landing_frame}): "
                                    "the shot boundary cuts the flight, so its end, distance and height are unknown",
                 ref=uid)
        return {"ok": False, "reason": "the shot ends before the flight does"}
    g_ok = abs(k.g_fit_rel_err) <= th["selfcheck"]["gravity_rel_tolerance"]
    s_ok = k.ax_rel_g <= th["selfcheck"]["sideways_rel_tolerance"]
    led.gate("G5 gravity", g_ok, f"{k.g_fit:.2f} m/s^2 from the flight ({k.g_fit_rel_err:+.1%} vs 9.81)", ref=uid)
    led.gate("G5 free flight", s_ok, f"sideways acceleration {k.ax_rel_g:.1%} of vertical"
             + (f"; {k.drag_like}" if k.drag_like and not (g_ok and s_ok) else ""), ref=uid)
    if tm["skipped"]:
        led.step("skipped frames", f"{len(tm['skipped'])} frames missing at a regular interval, re-inserted", ref=uid)
    return {"ok": True, "pts": tm["pts"], "k": k, "self_ok": g_ok and s_ok, "skipped": tm["skipped"],
            "attempts": tm["attempts"], "clip": clip}


def _audit_unit(bundle: Path, u: dict, cp: planmod.CheckedPlan, table, et, id_col, speed_col, unc_col, am, lam,
                out: Path, led: Ledger) -> dict:
    th = thresholds()
    uid = u["uid"]
    vrow = {"unit": uid, "video": u["unit"]["video"], "shot": u["unit"]["shot"], "frames": u["n_frames"],
            "shot_label": f"{u['unit']['shot']}" + (f" (recording {u['unit']['rec']})" if u["unit"].get("rec") else "")}
    if table is None or speed_col is None:
        led.gate("G4 comparison", False, "no single, absolute take-off speed column in an event table: nothing to "
                                         "compare a video measurement with, so the shot is not tracked", ref=uid)
        vrow.update(verdict=verdict.CANNOT_MEASURE, reason="no table of single-event speeds to compare with",
                    stage="inputs")
        return vrow
    if u["unit"].get("label") == "no recording proposed" and not u["frame_reading"].get("object_box"):
        led.gate("G2 recordings", False, "no recording in this shot: Muse Spark saw none on the contact sheet and no "
                                         "moving object on its first frame; not tracked", ref=uid)
        vrow.update(verdict=verdict.CANNOT_MEASURE, reason="no recording in this shot (e.g. a title card)",
                    stage="inputs")
        return vrow
    inputs = unit_inputs(u, cp, table, out, led, bundle)
    if not inputs["ok"]:
        vrow.update(verdict=verdict.CANNOT_MEASURE, reason=inputs["reason"], stage="inputs")
        return vrow
    m = measure_unit(bundle, u, inputs, cp.plan["object_phrase"], out, led)
    if not m["ok"]:
        vrow.update(verdict=verdict.CANNOT_MEASURE, reason=m["reason"], stage="track")
        return vrow
    k = m["k"]
    vrow.update(fps=inputs["fps"], fps_source=inputs["fps_source"], mm_per_px=inputs["mm_per_px"],
                kinematics=k.to_dict(), skipped_frames=len(m["skipped"]))
    pr = pairing.pair(k, table, cp.columns, id_col, th["pairing"]["min_margin"])
    led.gate("G3 blind pairing", pr["ok"], pr["reason"] + f" (features: {', '.join(pr.get('features', []))}; "
                                                          "published speed not used)", ref=uid)
    vrow["pairing"] = {kk: vv for kk, vv in pr.items() if kk != "detail"}
    vrow["pairing_detail"] = pr.get("detail")
    if not pr["ok"]:
        reason = "unpaired: " + pr["reason"]
        if not m["self_ok"]:
            reason = (f"self-checks failed (gravity {k.g_fit_rel_err:+.0%}, sideways {k.ax_rel_g:.0%} of vertical"
                      + (f"; {k.drag_like}" if k.drag_like else "") + "); " + reason)
        vrow.update(verdict=verdict.CANNOT_MEASURE, reason=reason)
        receipt.render(m["clip"], m["pts"], [
            f"Track: SAM 3.1, {len(m['pts'])} frames; take-off at frame {k.takeoff_frame}",
            f"Self-checks: gravity {k.g_fit:.2f} m/s^2 (9.81) | sideways {k.ax_rel_g:.0%} (0)",
            f"Blind pairing: {pr['reason'][:90]}"], verdict.CANNOT_MEASURE, out / "units" / uid / "receipt.mp4",
            takeoff_frame=k.takeoff_frame)
        return vrow
    rr = table.rows[pr["row_index"]]
    if not _finite(rr[speed_col["index"]]):
        led.gate("G6 published value", False, f"row {pr['row_id']} has no numeric value in {speed_col['name']}", ref=uid)
        vrow.update(verdict=verdict.CANNOT_MEASURE, reason="the paired row has no published speed")
        return vrow
    published = rr[speed_col["index"]] * speed_col["si_factor"]
    pm_val, pm_note = None, "no uncertainty column"
    if unc_col is not None and _finite(rr[unc_col["index"]]):
        raw = rr[unc_col["index"]]
        if unc_col["uncertainty_kind"] == "relative":
            pm_val, pm_note = raw * published, f"{unc_col['name']} = {raw:.3g} (relative, per the quote)"
        elif unc_col["uncertainty_kind"] == "absolute" and unc_col.get("si_factor"):
            pm_val, pm_note = raw * unc_col["si_factor"], f"{unc_col['name']} (absolute)"
        else:
            pm_note = f"{unc_col['name']}: meaning (absolute or relative) not established by the paper or script"
    mid, lo, hi = measure.speed_interval(k, inputs["scale_rel_unc"])
    tol = {"g_tol": th["selfcheck"]["gravity_rel_tolerance"], "free_flight_tol": th["selfcheck"]["sideways_rel_tolerance"]}
    v = verdict.decide(published, pm_val, mid, lo, hi, k.g_fit_rel_err, k.ax_rel_g, **tol)
    if pm_val is None and unc_col is not None and _finite(rr[unc_col["index"]]):
        # The ± exists but its meaning is unknown: decide only if both readings give the same verdict.
        raw = rr[unc_col["index"]]
        options = sorted((raw * published, raw * (unc_col.get("si_factor") or 1.0)))
        vs = [verdict.decide(published, x, mid, lo, hi, k.g_fit_rel_err, k.ax_rel_g, **tol) for x in options]
        readings = {x.label for x in vs}
        if len(readings) > 1:
            v = verdict.Verdict(verdict.CANNOT_MEASURE, published, None, mid, lo, hi, v.rel_diff,
                                f"the verdict depends on whether {unc_col['name']} is a relative or an absolute "
                                "uncertainty, and the paper does not say which")
        else:
            v, pm_val = vs[0], options[0]      # both readings agree; report the narrower ±
            pm_note += f"; both readings give {v.label}, the narrower ± is shown"
        led.gate("G6 uncertainty", len(readings) == 1, pm_note + f"; verdict under both readings: {sorted(readings)}",
                 ref=uid)
    if v.label == verdict.CANNOT_MEASURE and not m["self_ok"] and k.drag_like:
        v.reason += f"; {k.drag_like}"
    # Sensitivity: which published values this measurement would have accepted (same kind of ±).
    if pm_val is not None and unc_col is not None and unc_col["uncertainty_kind"] == "relative" and published:
        r = pm_val / published
        accept = [lo / (1 + r), hi / (1 - r) if r < 1 else float("inf")]
    else:
        pm_abs = pm_val or 0.0
        accept = [lo - pm_abs, hi + pm_abs]
    second = None
    if lam is not None:
        p = m["pts"]
        f_ = np.array([q.frame for q in p])
        if m["skipped"]:
            f_, _ = measure.repair_dropped_frames(f_, np.array([q.cx for q in p]), np.array([q.cy for q in p]),
                                                  inputs["mm_per_px"])
        second = measure.smoothing_spline_max(f_, np.array([q.cx for q in p]), np.array([q.cy for q in p]),
                                              inputs["fps"], inputs["mm_per_px"], lam)
    vrow.update(verdict=v.label, reason=v.reason, claim={"row": pr["row_id"], "value": published,
                                                          "plus_minus": pm_val, "plus_minus_note": pm_note,
                                                          "column": speed_col["name"]},
                measured={"mid": mid, "lo": lo, "hi": hi}, authors_method_replica=second,
                accepts_published=accept,
                authors_method=am if lam is not None else None)
    led.verdict({"unit": uid, "row": pr["row_id"], "label": v.label, "published": published, "pm": pm_val,
                 "interval": [lo, hi], "replica": second})
    header = [f"Claim ({Path(et['file']).name}, row {pr['row_id'][:28]}): take-off speed {published:.3f}"
              + (f" +/- {pm_val:.3f}" if pm_val else "") + " m/s",
              (f"Re-measured (SAM 3.1 track): {lo:.3f}-{hi:.3f} m/s" if v.label != verdict.CANNOT_MEASURE
               else "Re-measured: no speed reported, a self-check failed"),
              f"Self-checks: gravity {k.g_fit:.2f} m/s^2 (9.81) | sideways {k.ax_rel_g:.0%} (0) | paired blind, "
              f"margin {pr['margin']:.1f}x"]
    receipt.render(m["clip"], m["pts"], header, v.label, out / "units" / uid / "receipt.mp4",
                   takeoff_frame=k.takeoff_frame)
    return vrow



def run_audit(bundle: Path, out: Path, run_id: str | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    inv = ingest.inventory(bundle)
    led = Ledger(out / "ledger.json", run_id, inv.hashes, CHECKS)
    ing = ingest_stage(bundle, out, led)
    report = {"run_id": run_id, "bundle": bundle.name, "claims": [], "videos": []}
    if ing["licence"] is None:
        report["summary"] = {"claims": {}, "videos": {}, "stopped": "no open licence (CC BY, CC0 or public domain) "
                                                                     "stated in the paper; nothing was sent to the Model API"}
        (out / "report.json").write_text(json.dumps(report, indent=1))
        led.finish(status="stopped at G0: no open licence found; nothing was sent to the Model API")
        return report
    units = video_stage(bundle, ing, out, led)
    cp = plan_stage(ing, units, out, led)
    et = cp.plan.get("event_table")
    table = next((t for t in ing["tables"] if et and t.file == et["file"] and t.sheet == et["sheet"]), None)
    id_col = next((n for n, c in cp.columns.items() if c["quantity"] == "event_id"), None)
    speed_cols = [c for c in cp.columns.values() if c["quantity"] == "takeoff_speed" and c.get("si_factor")]
    speed_col = speed_cols[0] if len(speed_cols) == 1 else None
    if len(speed_cols) > 1:
        led.gate("G1 plan", False, f"several take-off speed columns ({', '.join(c['name'] for c in speed_cols)}): "
                                   "which one a video jump is compared with is ambiguous")
    unc_col = next((c for c in cp.columns.values() if c["quantity"] == "speed_uncertainty"
                    and speed_col and c.get("uncertainty_of") == speed_col["name"]), None)
    am = cp.plan.get("authors_speed_method", {})
    lam = _spar(am) if am.get("family") == "smoothing_spline_max" else None

    # The paper's own convention for '±', when it states one (e.g. "values are mean ± standard deviation").
    conv = re.search(r"means?\s*(?:±|\+/-|\+-)\s*(standard deviation|s\.?d\.?\b|sd\b|standard error|s\.?e\.?m?\.?\b)",
                     ingest.normalise(ing["pdf_text"]).replace("+/-", "±"), re.I)
    paper_spread = None if not conv else ("sd" if conv.group(1).lower().startswith(("standard d", "s.d", "sd")) else "se")
    if conv:
        led.step("spread convention", f"the paper states '{conv.group(0)}': a '±' of unknown type is read as "
                                      f"{paper_spread.upper()}")
    circ = re.search(r"mean vector|circular (?:mean|statistic|standard deviation)|watson.?williams|rayleigh test",
                     ingest.normalise(ing["pdf_text"]), re.I)
    if circ:
        led.step("angle statistics", f"the paper states '{circ.group(0)}': a mean angle that arithmetic does not "
                                     "reproduce is also tried as a circular mean (circular SD = sqrt(-2 ln R))")
    # claims from the PDF: routed by code
    for c in cp.claims:
        if c.get("spread") == "unknown" and c.get("plus_minus") is not None and paper_spread:
            c = dict(c, spread=paper_spread)
        route = planmod.needs(c)
        row = {"source": "paper", "quote": c["quote"], "quantity": c["quantity"], "value": c["value"],
               "plus_minus": c["plus_minus"], "unit": c["unit"], "statistic": c["statistic"], "route": route,
               "rows": (f"{c['row_filter']['column']} = {c['row_filter']['value']}"
                        if (c.get("row_filter") or {}).get("column") else "all")}
        if route.startswith("video") and c.get("table_column") and table is not None and \
                len(re.sub(r"[^0-9]", "", f"{c['value']:g}").lstrip("0")) >= 2:
            # Spark labelled it a single event, but if it equals a statistic of its column, it is one (code decides).
            for stat in ("mean", "max", "min"):
                res = tablecheck.check(dict(c, statistic=stat), table, cp.columns, bool(circ))
                if res["outcome"] != tablecheck.NOT_CHECKED:
                    led.gate("route", False, f"proposed as a single event, but it equals the {stat} of "
                                             f"'{res['column']}': routed to the table check")
                    route, c = "table_check", dict(c, statistic=stat)
                    row["statistic"], row["route"] = stat, route
                    break
        if route == "table_check" and table is not None:
            res = tablecheck.check(c, table, cp.columns, bool(circ))
            row.update(outcome=res["outcome"], reason=res["reason"],
                       evidence={k: v for k, v in res.items() if k not in ("outcome", "reason", "ok")})
        elif route == "table_check":
            row.update(outcome="NOT CHECKED", reason="no event table")
        elif route == "video":
            row.update(outcome="see video route", reason="single-event claims are matched to a video by pairing")
        else:
            row.update(outcome="REFUSED", reason=route.removeprefix("refuse: "))
        led.gate("route", row["outcome"] not in ("REFUSED",), f"{row['outcome']}: {c['quote'][:70]}")
        report["claims"].append(row)

    # video units: one failure (a crashed tool, an unreadable file) refuses that shot, not the audit
    for u in units:
        try:
            report["videos"].append(_audit_unit(bundle, u, cp, table, et, id_col, speed_col, unc_col, am, lam, out, led))
        except Exception as exc:
            led.gate("error", False, f"{type(exc).__name__}: {exc}", ref=u["uid"])
            report["videos"].append({"unit": u["uid"], "video": u["unit"]["video"], "shot": u["unit"]["shot"],
                                     "frames": u["n_frames"], "verdict": verdict.CANNOT_MEASURE,
                                     "reason": f"processing error: {type(exc).__name__}: {exc}", "stage": "error"})

    counts = {}
    for r in report["claims"]:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    report["summary"] = {"claims": counts, "videos": {u["unit"]: u["verdict"] for u in report["videos"]},
                         **led.proposals()}
    (out / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False, default=float))
    led.finish(status="complete", claims=counts, videos=report["summary"]["videos"])
    return report


def _finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _spar(am: dict) -> float | None:
    """The smoothing parameter the authors state (e.g. 'spar=1e-8', 'spar = 0.00000001', '10-8')."""
    text = am.get("parameters", "") + " " + am.get("evidence", "")
    m = re.search(r"spar\s*=\s*([0-9.eE+-]+)", text) or re.search(r"\b10\s*[-−–]\s*(\d+)\b", text)
    if not m:
        return None
    try:
        return float(m.group(1)) if "spar" in m.group(0) else 10 ** -int(m.group(1))
    except ValueError:
        return None
