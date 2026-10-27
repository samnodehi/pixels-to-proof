"""End-to-end run of one case. Every stage caches its output in the run folder, so a rerun costs nothing
and every intermediate result can be inspected."""
from __future__ import annotations

import json
import subprocess
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


def run(case_file: Path, out_dir: Path) -> dict:
    case = json.loads(case_file.read_text())
    base = case_file.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    log: dict = {"case": case["id"], "stages": {}}

    # 1. Spark reads the paper
    paper, usage = _cached(out_dir / "paper_reading.json",
                           lambda: list(read.read_paper(base / case["paper_pdf"])))
    log["stages"]["read_paper"] = {"claims_found": len(paper["claims"]), "usage": usage}

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

    # 3. time base: the case states it; Spark's reading of the overlay must agree
    fps = float(case["capture_fps"])
    spark_fps = frame_read.get("capture_fps")
    log["stages"]["time"] = {"capture_fps": fps, "spark_read_fps": spark_fps,
                             "agree": spark_fps is not None and abs(spark_fps - fps) < 1e-6}

    # 4. spatial scale: measured by OpenCV, compared with Spark's estimate
    band = frame_read.get("grid_band_rows") or None
    if band is not None and (len(band) != 2 or band[1] - band[0] < 50):
        band = None
    band = tuple(case.get("grid_band_rows") or band or (0, h))
    grid = scale.grid_from_frame(gray, axis="x", band=band)
    mm_per_px = grid.mm_per_px(float(case["grid_square_mm"]))
    est = frame_read.get("grid_square_px_estimate")
    log["stages"]["scale"] = {"spacing_px": grid.spacing_px, "spacing_sd_px": grid.spacing_sd_px,
                              "lines": len(grid.lines_px), "mm_per_px": mm_per_px,
                              "rel_unc": grid.rel_uncertainty(), "spark_estimate_px": est,
                              "spark_rel_diff": None if not est else scale.compare(est, grid.spacing_px)}

    # 5. SAM 3.1 tracks the object
    track_file = out_dir / "track.json"
    if not track_file.exists():
        fid = meta.upload(clip, "video/mp4")
        result = track.segment(fid, case.get("object_phrase") or paper["object_noun_phrase"])
        oid, pts = track.main_track(result)
        others = {k: len(v) for k, v in track.tracks(result).items() if k != oid}
        track.save_track(pts, track_file)
        (out_dir / "track_meta.json").write_text(json.dumps({"file_id": fid, "object_id": oid, "other_tracks": others}))
    pts = track.load_track(track_file)
    n_frames = int(cv2.VideoCapture(str(clip)).get(cv2.CAP_PROP_FRAME_COUNT))
    log["stages"]["track"] = {"frames_tracked": len(pts), "frames_in_clip": n_frames}

    # 6. kinematics, interval, verdict
    f = np.array([p.frame for p in pts])
    k = measure.kinematics(f, np.array([p.cx for p in pts]), np.array([p.cy for p in pts]), fps, mm_per_px)
    mid, lo, hi = measure.speed_interval(k, grid.rel_uncertainty())
    claim = case["claim"]
    v = verdict.decide(claim["value"], claim.get("plus_minus"), mid, lo, hi, k.g_fit_rel_err)
    log["kinematics"] = k.to_dict()
    log["verdict"] = v.to_dict()
    log["claim"] = claim

    # 7. receipt
    unc = f" +/- {claim['plus_minus']:.3f}" if claim.get("plus_minus") else ""
    header = [f"Claim ({claim['source_short']}): {claim['label']} {claim['value']:.3f}{unc} {claim['unit']}",
              f"Re-measured (SAM 3.1 track): {lo:.3f}-{hi:.3f} {claim['unit']} | gravity self-check "
              f"{k.g_fit:.2f} m/s^2"]
    receipt.render(clip, pts, header, v.label, out_dir / "receipt.mp4", takeoff_frame=k.takeoff_frame)
    (out_dir / "report.json").write_text(json.dumps(log, indent=2))
    return log
