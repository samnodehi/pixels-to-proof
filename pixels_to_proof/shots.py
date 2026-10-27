"""Split a supplementary video into shots (papers often concatenate several recordings)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np


def cuts(video: Path, threshold: float = 8.0) -> tuple[list[int], int, float]:
    """Frame indices where a new shot starts (mean abs difference of 160x90 grey thumbnails)."""
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    starts, prev, i = [0], None, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2GRAY).astype(np.float32)
        if prev is not None and float(np.abs(g - prev).mean()) > threshold:
            starts.append(i)
        prev, i = g, i + 1
    cap.release()
    return starts, i, fps


def shot_range(video: Path, shot: int) -> tuple[int, int]:
    """[first, last] frame of the 1-based shot number."""
    starts, total, _ = cuts(video)
    if not 1 <= shot <= len(starts):
        raise IndexError(f"Video has {len(starts)} shots; asked for shot {shot}.")
    first = starts[shot - 1]
    last = (starts[shot] - 1) if shot < len(starts) else total - 1
    return first, last


def extract(video: Path, first: int, last: int, dst: Path) -> Path:
    """Frame-exact extraction; output frame 0 == input frame `first`."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf",
                    f"select='between(n\\,{first}\\,{last})',setpts=N/FRAME_RATE/TB", "-an",
                    "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", str(dst)], check=True)
    return dst


def framed_panels(frame_bgr: np.ndarray, min_w: int = 200, min_h: int = 150) -> list[tuple[int, int, int, int]]:
    """Rectangles drawn around sub-videos in a montage (coloured borders), left to right, then top to bottom.
    Returned as (x, y, w, h) of the inside of the border."""
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    saturated = cv2.inRange(hsv, (0, 60, 40), (180, 255, 255))
    contours, _ = cv2.findContours(saturated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w >= min_w and h >= min_h:
            boxes.append((x + 6, y + 6, w - 12, h - 12))
    return sorted(boxes, key=lambda b: (round(b[1] / 50), b[0]))


def extract_region(video: Path, first: int, last: int, dst: Path, crop: tuple[int, int, int, int] | None = None) -> Path:
    """Frame-exact extraction of [first, last], optionally cropped to (x, y, w, h)."""
    vf = f"select='between(n\\,{first}\\,{last})',setpts=N/FRAME_RATE/TB"
    if crop:
        x, y, w, h = crop
        vf += f",crop={w - w % 2}:{h - h % 2}:{x}:{y}"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", vf, "-an",
                    "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", str(dst)], check=True)
    return dst


def median_frame(video: Path) -> np.ndarray:
    """Per-pixel median over the clip: removes the moving object, keeps the fixed scene (platforms, rulers)."""
    cap = cv2.VideoCapture(str(video))
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
    cap.release()
    if not frames:
        raise ValueError("empty clip")
    step = max(1, len(frames) // 120)
    return np.median(np.stack(frames[::step]), axis=0).astype(np.uint8)


def frame_at(video: Path, n: int, dst: Path) -> Path:
    """Exact frame n by decoding (OpenCV seeking is not frame-accurate on some codecs)."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"select='eq(n\\,{n})'",
                    "-frames:v", "1", "-vsync", "0", str(dst)], check=True)
    return dst
