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


def ranges(video: Path, cut_threshold: float = 8.0, lag: int = 10, fade_changed: float = 0.5,
           fade_brightness: float = 12.0) -> tuple[list[tuple[int, int]], int]:
    """Shots as [first, last] frame ranges. Besides hard cuts, gradual transitions (fades and cross-fades between
    recordings of different brightness) are found where, between frames i-lag and i+lag, most of the picture changes
    AND its mean brightness moves; the frames of such a span belong to no shot. A span that contains a hard cut, or is
    shorter than `lag` frames, is left to the cut detector. Handheld motion changes many pixels but not the mean
    brightness, so it is not taken for a fade."""
    cap = cv2.VideoCapture(str(video))
    thumbs = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        thumbs.append(cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2GRAY))
    cap.release()
    n = len(thumbs)
    if n == 0:
        return [], 0
    T = np.stack(thumbs).astype(np.float32)     # 160x90 per frame; ~58 kB as float32
    step = np.concatenate([[0.0], np.abs(np.diff(T, axis=0)).mean(axis=(1, 2))])
    cut_at = set(np.where(step > cut_threshold)[0].tolist())
    mean = T.mean(axis=(1, 2))
    fade = np.zeros(n, bool)
    for i in range(lag, n - lag):
        fade[i] = (np.abs(T[i + lag] - T[i - lag]) > 12).mean() > fade_changed and \
            abs(mean[i + lag] - mean[i - lag]) > fade_brightness
    spans, i = [], 0
    while i < n:
        if fade[i]:
            j = i
            while j + 1 < n and (fade[j + 1] or (j + 3 < n and fade[j + 2:j + 4].any())):
                j += 1
            if j - i + 1 >= lag and not any(i <= c <= j for c in cut_at):
                spans.append((i, j))
            i = j + 1
        else:
            i += 1
    # boundaries: hard cuts start a new shot; a fade span removes its own frames
    blocked = np.zeros(n, bool)
    for a, b in spans:
        blocked[a:b + 1] = True
    out, start = [], None
    for f in range(n):
        if blocked[f]:
            if start is not None:
                out.append((start, f - 1))
                start = None
            continue
        if start is None:
            start = f
        elif f in cut_at:
            out.append((start, f - 1))
            start = f
    if start is not None:
        out.append((start, n - 1))
    return out, n


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


def contact_sheet(video: Path, first: int, last: int, dst: Path, tiles: int = 48, cols: int = 8,
                  tile_w: int = 240) -> list[int]:
    """Evenly spaced frames of [first, last] tiled into one image, each labelled with its frame number.
    Returns the sampled frame numbers."""
    n = last - first + 1
    picks = sorted({first + round(i * (n - 1) / max(tiles - 1, 1)) for i in range(min(tiles, n))})
    want, got = set(picks), {}
    cap = cv2.VideoCapture(str(video))
    i = 0
    while i <= last:
        ok, frame = cap.read()
        if not ok:
            break
        if i in want:
            h, w = frame.shape[:2]
            t = cv2.resize(frame, (tile_w, round(h * tile_w / w)), interpolation=cv2.INTER_AREA)
            cv2.putText(t, str(i), (5, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(t, str(i), (5, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
            got[i] = t
        i += 1
    cap.release()
    picks = [p for p in picks if p in got]
    th = got[picks[0]].shape[0]
    rows = []
    for r in range(0, len(picks), cols):
        row = [got[p] for p in picks[r:r + cols]]
        row += [np.zeros_like(row[0])] * (cols - len(row))
        rows.append(np.hstack(row))
    cv2.imwrite(str(dst), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return picks
