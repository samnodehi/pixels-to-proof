"""Visual receipt: the clip with the measured track, the claim and the verdict burned in."""
from __future__ import annotations

import subprocess
from pathlib import Path

import cv2

from .track import Point

GREEN, RED, AMBER, WHITE = (80, 220, 120), (60, 60, 235), (0, 190, 255), (255, 255, 255)


def render(clip: Path, points: list[Point], header: list[str], verdict_label: str, out: Path,
           takeoff_frame: int | None = None) -> Path:
    colour = {"REPRODUCED": GREEN, "NOT REPRODUCED": RED}.get(verdict_label, AMBER)
    by_frame = {p.frame: p for p in points}
    cap = cv2.VideoCapture(str(clip))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    tmp = out.with_suffix(".raw.mp4")
    writer = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    bar = 34 * (len(header) + 1) + 10
    trail: list[tuple[int, int]] = []
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i in by_frame:
            p = by_frame[i]
            trail.append((int(round(p.cx)), int(round(p.cy))))
            cv2.rectangle(frame, (p.left, p.top), (p.right, p.bottom), WHITE, 1)
        for a, b in zip(trail, trail[1:]):
            cv2.line(frame, a, b, AMBER, 3, cv2.LINE_AA)
        if takeoff_frame is not None and takeoff_frame in by_frame and i >= takeoff_frame:
            q = by_frame[takeoff_frame]
            cv2.circle(frame, (int(q.cx), int(q.cy)), 9, colour, 2, cv2.LINE_AA)
        if trail:
            cv2.circle(frame, trail[-1], 6, (0, 0, 255), -1, cv2.LINE_AA)
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, bar), (18, 18, 18), -1)
        frame = cv2.addWeighted(overlay, 0.85, frame, 0.15, 0)
        for k, line in enumerate(header):
            cv2.putText(frame, line, (16, 30 + 34 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.72, WHITE, 2, cv2.LINE_AA)
        cv2.putText(frame, verdict_label, (16, 30 + 34 * len(header)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, colour, 2,
                    cv2.LINE_AA)
        writer.write(frame)
        i += 1
    writer.release()
    cap.release()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "23", "-preset", "veryfast", str(out)], check=True)
    tmp.unlink(missing_ok=True)
    return out
