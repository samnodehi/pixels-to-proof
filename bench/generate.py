"""Synthetic calibration set: videos with exactly known take-off speed, plus planted claim errors.

Each case is a high-speed recording rendered from physics: a ball rests on a floor in front of a 5 mm grid,
launches with a known speed and angle, flies ballistically (g = 9.80665) and lands. The video carries the same
kind of overlay text real supplementary videos do. A claim is attached whose value is the truth times
(1 + planted error), so the benchmark measures detection power and false alarms of the whole pipeline.

Usage: python -m bench.generate OUT_DIR --n 48 --seed 1
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

G = 9.80665
W, H = 1280, 720
ERRORS = [0.0, 0.0, 0.01, -0.01, 0.05, -0.05, 0.10, -0.10, 0.20, -0.20, 0.0, 0.05]


def background(rng, px_per_mm: float) -> np.ndarray:
    tint = rng.uniform(200, 235)
    img = np.full((H, W, 3), tint, np.float32)
    img += rng.normal(0, 2.0, img.shape)
    sq = 5.0 * px_per_mm
    x0, y0 = rng.uniform(0, sq), rng.uniform(0, sq)
    for x in np.arange(x0, W, sq):
        cv2.line(img, (int(round(x)), 0), (int(round(x)), H), (110, 110, 110), 3, cv2.LINE_AA)
    for y in np.arange(y0, H, sq):
        cv2.line(img, (0, int(round(y))), (W, int(round(y))), (110, 110, 110), 3, cv2.LINE_AA)
    floor = int(H * 0.86)
    img[floor:, :] = rng.uniform(170, 200)
    return np.clip(img, 0, 255).astype(np.uint8), floor


def render_case(out: Path, idx: int, rng: np.random.Generator) -> dict:
    fps = float(rng.choice([1000, 2000, 3200, 5000]))
    v0 = float(rng.uniform(0.3, 1.0))
    angle = float(rng.uniform(25, 80))
    vx, vy = v0 * np.cos(np.radians(angle)), v0 * np.sin(np.radians(angle))
    t_flight = 2 * vy / G
    height_m, range_m = vy ** 2 / (2 * G), vx * t_flight
    # choose a scale so the whole flight fits in the frame with margin
    px_per_mm = float(min(0.75 * W / (range_m * 1000 + 8), 0.6 * H / (height_m * 1000 + 6), 40.0))
    if px_per_mm < 8.0:
        raise ValueError("flight too large for the frame")
    bg, floor = background(rng, px_per_mm)
    r_px = max(10, int(round(rng.uniform(1.0, 2.0) * px_per_mm)))
    colour = tuple(int(c) for c in rng.integers(30, 140, 3))
    rest = int(rng.integers(20, 60))
    n_flight = int(np.ceil(t_flight * fps))
    n_frames = rest + n_flight + 30
    if n_frames > 900:  # keep clips short: long streams were observed to drop
        raise ValueError("too long")
    x_start = int(W * 0.12)
    y_ground = floor - r_px
    raw = out / f"case_{idx:03d}" / "video_raw.mp4"
    raw.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), 30, (W, H))
    text = ["Synthetic calibration case", f"captured - {int(fps):,} frames/second", "playback - 30 frames/second"]
    for i in range(n_frames):
        t = (i - rest) / fps
        if i < rest:
            x_m, y_m = 0.0, 0.0
        elif t <= t_flight:
            x_m, y_m = vx * t, vy * t - 0.5 * G * t * t
        else:
            x_m, y_m = range_m, 0.0
        cx = x_start + x_m * 1000 * px_per_mm
        cy = y_ground - y_m * 1000 * px_per_mm
        frame = bg.copy()
        cv2.circle(frame, (int(round(cx)), int(round(cy))), r_px, colour, -1, cv2.LINE_AA)
        cv2.circle(frame, (int(round(cx - r_px * 0.3)), int(round(cy - r_px * 0.3))), max(2, r_px // 4),
                   tuple(min(255, c + 80) for c in colour), -1, cv2.LINE_AA)
        frame = cv2.GaussianBlur(frame, (3, 3), 0)
        for k, line in enumerate(text):
            cv2.putText(frame, line, (14, H - 70 + 24 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
                        cv2.LINE_AA)
        writer.write(frame)
    writer.release()
    video = raw.with_name("video.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "18", str(video)], check=True)
    raw.unlink()
    err = float(ERRORS[idx % len(ERRORS)])
    wrong_fps = idx % 12 == 11      # adversarial: the case states the wrong frame rate
    case = {
        "id": f"synthetic_{idx:03d}", "synthetic": True, "video": "video.mp4", "shot": 1,
        "capture_fps": fps / 2 if wrong_fps else fps, "grid_square_mm": 5.0, "object_phrase": "ball",
        "claim": {"label": "take-off speed", "value": round(v0 * (1 + err), 4), "plus_minus": None, "unit": "m/s",
                  "source_short": f"synthetic {idx:03d}", "provenance": "planted"},
        "truth": {"v0": v0, "angle_deg": angle, "fps": fps, "px_per_mm": px_per_mm, "planted_error": err,
                  "wrong_fps_in_case": wrong_fps, "expected": ("CANNOT MEASURE" if wrong_fps else
                                                               ("REPRODUCED" if err == 0 else "NOT REPRODUCED"))},
    }
    (raw.parent / "case.json").write_text(json.dumps(case, indent=2))
    return case


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--n", type=int, default=48)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    made, idx = 0, 0
    while made < a.n:
        try:
            render_case(a.out, idx, rng)
            made += 1
            idx += 1
        except ValueError:
            continue
    print(f"{made} cases in {a.out}")


if __name__ == "__main__":
    main()
