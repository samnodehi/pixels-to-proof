"""Pixels to Proof - web app (Hugging Face Space).

Shows the verified cases and the calibration benchmark from stored runs, and lets a visitor run the full
pipeline on their own clip. Live runs use the Space's MODEL_API_KEY secret and are rate limited."""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import shutil
import tempfile
import threading
from pathlib import Path

import gradio as gr

ROOT = Path(__file__).parent
SHOWCASE = ROOT / "showcase"
MAX_RUNS_PER_DAY = int(os.environ.get("P2P_MAX_RUNS_PER_DAY", "15"))
MAX_VIDEO_MB = 40

_lock = threading.Lock()
_runs = {"day": dt.date.today(), "n": 0}


def _fmt(x: float, unit: str = "") -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.3f}{(' ' + unit) if unit else ''}"


def verdict_card(report: dict) -> str:
    v, c = report["verdict"], report["claim"]
    colour = {"REPRODUCED": "#1f9d55", "NOT REPRODUCED": "#cc3333"}.get(v["label"], "#b7791f")
    unc = f" ± {c['plus_minus']:.3f}" if c.get("plus_minus") else ""
    k = report.get("kinematics", {})
    lines = [
        f"<div style='border-left:6px solid {colour};padding:8px 14px'>",
        f"<div style='font-size:1.6em;font-weight:700;color:{colour}'>{v['label']}</div>",
        f"<div><b>Claim</b> ({c.get('source_short', '')}): {c['label']} = <b>{c['value']:.3f}{unc} {c['unit']}</b></div>",
        f"<div><b>Re-measured from the video</b>: {_fmt(v['measured_mid'])} {c['unit']} "
        f"(interval {_fmt(v['measured_lo'])} – {_fmt(v['measured_hi'])})</div>",
    ]
    if k:
        lines.append(f"<div><b>Gravity self-check</b>: {k['g_fit']:.2f} m/s² (expected 9.81) · "
                     f"take-off angle {k['angle_deg']:.1f}° · height {k['height_mm']:.2f} mm · "
                     f"airborne {k['airborne_s'] * 1000:.1f} ms</div>")
    lines.append(f"<div style='opacity:.8'><b>Why</b>: {v['reason']}</div></div>")
    return "\n".join(lines)


def evidence_md(report: dict) -> str:
    s = report["stages"]
    out = ["| stage | who | result |", "|---|---|---|"]
    if "read_paper" in s:
        out.append(f"| read the paper | Muse Spark 1.3 | {s['read_paper']['claims_found']} kinematic claims extracted with quotes |")
    t = s.get("time", {})
    if t:
        out.append(f"| time base | Muse Spark 1.3 (overlay) + case | {t['capture_fps']:.0f} fps from {t.get('source', 'case')}; "
                   f"Spark read {t.get('spark_read_fps')} |")
    sc = s.get("scale")
    if sc:
        sp = sc.get("spark_rel_diff")
        out.append(f"| scale | OpenCV, checked against Muse Spark | grid {sc['spacing_px']:.1f} px (sd {sc['spacing_sd_px']:.2f}, "
                   f"{sc['lines']} lines); Spark's estimate off by {sp:.0%} |" if sp is not None else
                   f"| scale | OpenCV | grid {sc['spacing_px']:.1f} px |")
    tr = s.get("track")
    if tr:
        acc = next((a for a in tr["attempts"] if a["accepted"]), None)
        rej = [a for a in tr["attempts"] if not a["accepted"]]
        txt = (f"{tr.get('frames_tracked', 0)}/{tr['frames_in_clip']} frames, prompt: {acc['prompt']}" if acc else "no usable track")
        if rej:
            txt += f"; rejected: {'; '.join(a['prompt'] + ' (' + a['reason'] + ')' for a in rej)}"
        out.append(f"| track | SAM 3.1 | {txt} |")
    k = report.get("kinematics")
    if k:
        out.append(f"| measure | code (ballistic fit, block bootstrap) | v0 {k['v0_ballistic']:.3f} m/s, 95% CI "
                   f"{k['v0_ci95'][0]:.3f}–{k['v0_ci95'][1]:.3f}; spline method {k['v_max_spline']:.3f} |")
    return "\n".join(out)


def showcase_cases() -> list[dict]:
    cases = []
    for d in sorted(p for p in SHOWCASE.glob("*") if p.is_dir() and (p / "report.json").exists()):
        meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
        cases.append({"dir": d, "report": json.loads((d / "report.json").read_text()), "meta": meta})
    return cases


def _quota() -> bool:
    with _lock:
        if _runs["day"] != dt.date.today():
            _runs.update(day=dt.date.today(), n=0)
        if _runs["n"] >= MAX_RUNS_PER_DAY:
            return False
        _runs["n"] += 1
        return True


def live_run(video, pdf, shot, value, plus_minus, unit, label, square_mm, fps, phrase):
    from pixels_to_proof.pipeline import run  # imported lazily so the showcase loads without a key

    if not os.environ.get("MODEL_API_KEY"):
        yield None, "Live runs are disabled: this Space has no MODEL_API_KEY secret.", ""
        return
    if video is None or value in (None, ""):
        yield None, "Upload a video and enter the published value.", ""
        return
    if Path(video).stat().st_size > MAX_VIDEO_MB * 1e6:
        yield None, f"Video larger than {MAX_VIDEO_MB} MB.", ""
        return
    if not _quota():
        yield None, f"Daily limit of {MAX_RUNS_PER_DAY} live runs reached. The stored cases above show full runs.", ""
        return
    work = Path(tempfile.mkdtemp(prefix="p2p_"))
    shutil.copy(video, work / "video.mp4")
    case = {"id": "live", "video": "video.mp4", "shot": int(shot or 1),
            "capture_fps": float(fps) if fps else None, "grid_square_mm": float(square_mm) if square_mm else None,
            "object_phrase": phrase or None,
            "claim": {"label": label or "take-off speed", "value": float(value),
                      "plus_minus": float(plus_minus) if plus_minus else None, "unit": unit or "m/s",
                      "source_short": "your input"}}
    if pdf is not None:
        shutil.copy(pdf, work / "paper.pdf")
        case["paper_pdf"] = "paper.pdf"
    (work / "case.json").write_text(json.dumps(case))
    yield None, "Running: Muse Spark reads the frame and the paper → OpenCV measures the scale → SAM 3.1 tracks → physics. About 2–4 minutes.", ""
    try:
        report = run(work / "case.json", work / "run")
    except Exception as exc:  # shown to the user; the pipeline itself never invents a number
        yield None, f"Run failed: {type(exc).__name__}: {exc}", ""
        return
    rec = work / "run" / "receipt.mp4"
    yield (str(rec) if rec.exists() else None), verdict_card(report), evidence_md(report)


INTRO = """
# Pixels to Proof
**Re-measure a number a scientific paper published — from the paper's own video.**

1. **Muse Spark 1.3** reads the paper and the video: the claim, the frame rate printed on the video, the scale reference, and where the object is.
2. **SAM 3.1** follows that object through every frame (Spark's box tells it which one).
3. **Code measures** — grid scale with OpenCV, a ballistic fit of the flight, a **gravity self-check** (the fit must find 9.81 m/s², or the scale or frame rate is wrong), a bootstrap interval.
4. **Verdict**: REPRODUCED · NOT REPRODUCED · CANNOT MEASURE, with a visual receipt.

*The model proposes; tracking and physics decide. No number in a verdict is written by a language model.*
"""


def build() -> gr.Blocks:
    with gr.Blocks(title="Pixels to Proof") as demo:
        gr.Markdown(INTRO)
        with gr.Tab("Verified cases"):
            for c in showcase_cases():
                m = c["meta"]
                gr.Markdown(f"### {m.get('title', c['dir'].name)}\n{m.get('citation', '')}  \n*Licence: {m.get('licence', '')}*")
                with gr.Row():
                    gr.Video(str(c["dir"] / "receipt.mp4"), label="Receipt", autoplay=False)
                    with gr.Column():
                        gr.HTML(verdict_card(c["report"]))
                        if m.get("note"):
                            gr.Markdown(m["note"])
                gr.Markdown(evidence_md(c["report"]))
                if (c["dir"] / "scale_evidence.png").exists():
                    gr.Image(str(c["dir"] / "scale_evidence.png"), label="Scale evidence: measured grid lines (green), Spark's object box (orange)")
                if m.get("provenance"):
                    with gr.Accordion("Where the claim comes from", open=False):
                        gr.Markdown(m["provenance"])
        with gr.Tab("Calibration"):
            cal = SHOWCASE / "calibration.md"
            gr.Markdown(cal.read_text() if cal.exists() else "Calibration results not bundled.")
        with gr.Tab("Try it"):
            gr.Markdown("Upload a high-speed clip of **one object in free flight in front of a square grid** "
                        "(a jump, a throw, a drop). Enter the number the paper claims. Live runs are limited per day.")
            with gr.Row():
                video = gr.File(label="Video (mp4, ≤ 40 MB)", file_types=[".mp4", ".mov", ".avi"])
                pdf = gr.File(label="Paper PDF (optional)", file_types=[".pdf"])
            with gr.Row():
                value = gr.Number(label="Published value")
                plus_minus = gr.Number(label="± (optional)")
                unit = gr.Textbox(value="m/s", label="Unit")
                label = gr.Textbox(value="take-off speed", label="Quantity")
            with gr.Row():
                shot = gr.Number(value=1, precision=0, label="Shot number in the video")
                square_mm = gr.Number(label="Grid square size, mm (blank = from the paper)")
                fps = gr.Number(label="Capture fps (blank = read from the video by Spark)")
                phrase = gr.Textbox(label="Object name (optional, e.g. 'larva')")
            go = gr.Button("Re-measure", variant="primary")
            out_video = gr.Video(label="Receipt")
            out_card = gr.HTML()
            out_ev = gr.Markdown()
            go.click(live_run, [video, pdf, shot, value, plus_minus, unit, label, square_mm, fps, phrase],
                     [out_video, out_card, out_ev], concurrency_limit=1)
        gr.Markdown("Built for the Meta Global AI Developer Hackathon 2026 with Muse Spark 1.3 and SAM 3.1 (Meta Model API). "
                    "Source: github.com/samnodehi/pixels-to-proof")
    return demo


if __name__ == "__main__":
    build().launch(theme=gr.themes.Soft())
