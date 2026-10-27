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
