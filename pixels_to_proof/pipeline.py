"""End-to-end run of one case. Every stage caches its output in the run folder, so a rerun costs nothing
and every intermediate result can be inspected."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np

from . import measure, meta, read, receipt, scale, shots, track, verdict


def _cached(path: Path, fn):
    if path.exists():
        return json.loads(path.read_text())
    value = fn()
    path.write_text(json.dumps(value, indent=2))
    return value


def _scale_evidence(frame_png: Path, grid: scale.GridScale, band, box, out: Path) -> None:
    """Frame 0 with the measured grid lines (green), the band used (blue) and Spark's object box (orange)."""
    img = cv2.imread(str(frame_png))
    for x in grid.lines_px:
        cv2.line(img, (int(round(x)), int(band[0])), (int(round(x)), int(band[1])), (80, 220, 120), 2)
    cv2.rectangle(img, (0, int(band[0])), (img.shape[1] - 1, int(band[1])), (255, 140, 0), 2)
    if box and len(box) == 4:
        cv2.rectangle(img, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), (0, 165, 255), 2)
    cv2.putText(img, f"grid {grid.spacing_px:.1f} px (sd {grid.spacing_sd_px:.2f})", (16, int(band[0]) + 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (80, 220, 120), 2, cv2.LINE_AA)
    cv2.imwrite(str(out), img)


def _cannot(log: dict, case: dict, out_dir: Path, reason: str) -> dict:
    claim = case["claim"]
    nan = float("nan")
    log["verdict"] = verdict.Verdict(verdict.CANNOT_MEASURE, claim["value"], claim.get("plus_minus"),
                                     nan, nan, nan, nan, reason).to_dict()
    log["claim"] = claim
    (out_dir / "report.json").write_text(json.dumps(log, indent=2))
    return log


def run(case_file: Path, out_dir: Path) -> dict:
    case = json.loads(case_file.read_text())
    base = case_file.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    log: dict = {"case": case["id"], "stages": {}, "timing_s": {}}
    clock = [time.perf_counter()]

    def tick(name: str) -> None:
        now = time.perf_counter()
        log["timing_s"][name] = round(now - clock[0], 2)
        clock[0] = now

    # 1. Spark reads the paper
    paper: dict = {}
    if case.get("paper_pdf"):
        paper, usage = _cached(out_dir / "paper_reading.json",
                               lambda: list(read.read_paper(base / case["paper_pdf"])))
        log["stages"]["read_paper"] = {"claims_found": len(paper["claims"]), "usage": usage}

    tick("read_paper")
    # 2. the analysed clip and its first frame
    clip = out_dir / "clip.mp4"
    first, last = shots.shot_range(base / case["video"], int(case["shot"]))
    log["stages"]["shot"] = {"shot": case["shot"], "first_frame": first, "last_frame": last}
    if not clip.exists():
        shots.extract(base / case["video"], first, last, clip)
    frame_png = out_dir / "frame0.png"
    if not frame_png.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-frames:v", "1", str(frame_png)], check=True)
    gray = cv2.imread(str(frame_png), cv2.IMREAD_GRAYSCALE)
    h, w = gray.shape
    frame_read, usage = _cached(out_dir / "frame_reading.json", lambda: list(read.read_frame(frame_png, w, h)))
    log["stages"]["read_frame"] = {"usage": usage}

    tick("shot_and_read_frame")
    # 3. time base: stated by the case, else read by Spark from the overlay, else the paper's video legend.
    #    When both the case and Spark give one, they must agree (logged; the gravity check is the real test).
    spark_fps = frame_read.get("capture_fps")
    paper_fps = next((v.get("capture_fps") for v in paper.get("videos", []) if v.get("capture_fps")), None)
    stated = case.get("capture_fps")
    fps_source = "case" if stated else ("Muse Spark (video overlay)" if spark_fps else ("Muse Spark (paper)" if paper_fps else None))
    if fps_source is None:
        return _cannot(log, case, out_dir, "no capture frame rate stated in the case, the video overlay or the paper")
    fps = float(stated or spark_fps or paper_fps)
    log["stages"]["time"] = {"capture_fps": fps, "source": fps_source, "spark_read_fps": spark_fps,
                             "agree": spark_fps is not None and abs(float(spark_fps) - fps) < 1e-6}

    # 4. spatial scale: measured by OpenCV, compared with Spark's estimate
    band = frame_read.get("grid_band_rows") or None
    if band is not None and (len(band) != 2 or band[1] - band[0] < 50):
        band = None
    band = tuple(case.get("grid_band_rows") or band or (0, h))
    square_mm = case.get("grid_square_mm") or paper.get("scale_reference_mm")
    if not square_mm:
        return _cannot(log, case, out_dir, "the real size of the grid square is not known")
    try:
        grid = scale.grid_from_frame(gray, axis="x", band=band)
    except ValueError as exc:
        return _cannot(log, case, out_dir, f"no measurable grid: {exc}")
    mm_per_px = grid.mm_per_px(float(square_mm))
    est = frame_read.get("grid_square_px_estimate")
    _scale_evidence(frame_png, grid, band, frame_read.get("object_box"), out_dir / "scale_evidence.png")
    log["stages"]["scale"] = {"spacing_px": grid.spacing_px, "spacing_sd_px": grid.spacing_sd_px,
                              "lines": len(grid.lines_px), "mm_per_px": mm_per_px,
                              "rel_unc": grid.rel_uncertainty(), "spark_estimate_px": est,
                              "spark_rel_diff": None if not est else scale.compare(est, grid.spacing_px)}

    tick("scale")
    # 5-6. SAM 3.1 tracks the object; kinematics are computed per prompt attempt. A track that never leaves
    # the ground or whose mask area jumps (SAM switched to background) is rejected and the next prompt is tried.
    phrase = case.get("object_phrase") or paper.get("object_noun_phrase", "object")
    box = frame_read.get("object_box") or []
    prompts = []
    if len(box) == 4:   # Spark's grounding on frame 0 tells SAM which object to follow
        prompts.append(("box from Muse Spark", track.box_prompt(box, (w, h))))
    prompts.append((f"text '{phrase}'", phrase))
    claim = case["claim"]
    n_frames = int(cv2.VideoCapture(str(clip)).get(cv2.CAP_PROP_FRAME_COUNT))
    file_id = None
    attempts, chosen = [], None
    for n, (how, prompt) in enumerate(prompts):
        tfile = out_dir / f"track_{n}.json"
        if not tfile.exists():
            file_id = file_id or meta.upload(clip, "video/mp4")
            try:
                result = track.segment(file_id, prompt)
                _, pts_n = track.main_track(result)
                track.save_track(pts_n, tfile)
            except (LookupError, RuntimeError) as exc:
                attempts.append({"prompt": how, "accepted": False, "reason": str(exc)})
                continue
        pts_n = track.load_track(tfile)
        quality = track.quality(pts_n)
        if not quality["ok"]:
            attempts.append({"prompt": how, "accepted": False, "reason": quality["reason"], "quality": quality})
            continue
        try:
            f = np.array([p.frame for p in pts_n])
            k = measure.kinematics(f, np.array([p.cx for p in pts_n]), np.array([p.cy for p in pts_n]), fps, mm_per_px)
        except ValueError as exc:
            attempts.append({"prompt": how, "accepted": False, "reason": str(exc), "quality": quality})
            continue
        attempts.append({"prompt": how, "accepted": True, "quality": quality})
        chosen = (pts_n, k)
        break
    log["stages"]["track"] = {"frames_in_clip": n_frames, "attempts": attempts}
    if chosen is None:
        return _cannot(log, case, out_dir, "no usable track: " + "; ".join(a["reason"] for a in attempts))
    pts, k = chosen
    log["stages"]["track"]["frames_tracked"] = len(pts)
    mid, lo, hi = measure.speed_interval(k, grid.rel_uncertainty())
    v = verdict.decide(claim["value"], claim.get("plus_minus"), mid, lo, hi, k.g_fit_rel_err)
    log["kinematics"] = k.to_dict()
    log["verdict"] = v.to_dict()
    log["claim"] = claim

    tick("track_and_measure")
    # 7. receipt
    unc = f" +/- {claim['plus_minus']:.3f}" if claim.get("plus_minus") else ""
    header = [f"Claim ({claim['source_short']}): {claim['label']} {claim['value']:.3f}{unc} {claim['unit']}",
              f"Re-measured (SAM 3.1 track): {lo:.3f}-{hi:.3f} {claim['unit']} | gravity self-check "
              f"{k.g_fit:.2f} m/s^2"]
    receipt.render(clip, pts, header, v.label, out_dir / "receipt.mp4", takeoff_frame=k.takeoff_frame)
    tick("receipt")
    (out_dir / "report.json").write_text(json.dumps(log, indent=2))
    return log
