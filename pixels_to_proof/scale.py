"""Spatial scale from pixels. Muse Spark proposes what the reference is; this module measures it."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class GridScale:
    spacing_px: float        # mean distance between adjacent grid lines
    spacing_sd_px: float     # spread of the individual spacings
    lines_px: list[float]    # line centres along the measured axis
    axis: str                # "x" (vertical lines) or "y" (horizontal lines)

    def mm_per_px(self, square_mm: float) -> float:
        return square_mm / self.spacing_px

    def rel_uncertainty(self) -> float:
        # standard error of the mean spacing, relative
        n = max(len(self.lines_px) - 1, 1)
        return (self.spacing_sd_px / np.sqrt(n)) / self.spacing_px


def _line_centres(profile: np.ndarray, k: float) -> list[float]:
    thr = profile.mean() - k * profile.std()
    idx = np.where(profile < thr)[0]
    if len(idx) == 0:
        return []
    groups, cur = [], [idx[0]]
    for i in idx[1:]:
        if i - cur[-1] <= 2:
            cur.append(i)
        else:
            groups.append(cur)
            cur = [i]
    groups.append(cur)
    return [float(np.average(g, weights=thr - profile[g])) for g in groups if len(g) >= 2]


def grid_from_frame(gray: np.ndarray, axis: str = "x", band: tuple[int, int] | None = None,
                    k: float = 1.0) -> GridScale:
    """Dark grid lines on a light background. `band` limits the rows (axis x) or columns (axis y)
    used for the profile, so the object, the floor or overlay text do not bias it."""
    if axis == "x":
        rows = gray if band is None else gray[band[0]:band[1], :]
        profile = rows.mean(axis=0)
    else:
        cols = gray if band is None else gray[:, band[0]:band[1]]
        profile = cols.mean(axis=1)
    lines = _line_centres(profile.astype(float), k)
    if len(lines) < 3:
        raise ValueError(f"Found {len(lines)} grid lines on axis {axis}; need at least 3.")
    d = np.diff(lines)
    med = float(np.median(d))
    # Keep spacings close to the median: drops partial lines at the edges and the floor line.
    good = d[np.abs(d - med) < 0.1 * med]
    if len(good) < 2:
        raise ValueError("Grid spacing is not regular enough to measure.")
    return GridScale(spacing_px=float(good.mean()), spacing_sd_px=float(good.std(ddof=1)),
                     lines_px=lines, axis=axis)


def compare(proposed_px: float, measured_px: float) -> float:
    """Relative disagreement between the model's proposal and the measurement."""
    return abs(proposed_px - measured_px) / measured_px


@dataclass
class GapScale:
    left_tip_px: float
    right_tip_px: float
    left_row: int
    right_row: int

    @property
    def gap_px(self) -> float:
        return self.right_tip_px - self.left_tip_px

    def mm_per_px(self, gap_mm: float) -> float:
        return gap_mm / self.gap_px

    def rel_uncertainty(self) -> float:
        # each tip located to about +/-2 px (edge blur on a 1-2 px rod end)
        return float(np.hypot(2.0, 2.0) / self.gap_px)


def platform_gap(median_gray: np.ndarray) -> GapScale:
    """Two horizontal platforms (rods) entering from the left and right edges, as in take-off / landing setups.
    Uses the vertical-gradient band of each rod and walks along it to the rod's free end."""
    import cv2

    img = median_gray.astype(np.float32)
    h, w = img.shape
    gy = np.abs(cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3))

    def run_from_edge(row: int, side: str) -> int:
        band = gy[max(0, row - 4):row + 5, :].max(axis=0)
        ref = band[: int(w * 0.1)] if side == "L" else band[int(w * 0.9):]
        on = band > 0.5 * float(np.median(ref))
        if side == "L":
            x = 0
            while x < w - 1 and (on[x] or on[x + 1:x + 4].any()):
                x += 1
            return x
        x = w - 1
        while x > 0 and (on[x] or on[max(0, x - 3):x].any()):
            x -= 1
        return x

    def tip(side: str) -> tuple[int, int]:
        # A platform is a horizontal edge pair that starts at the image border and runs inwards. Among the rows
        # with the strongest vertical gradient near that border, take the one with the longest run.
        cols = slice(0, int(w * 0.15)) if side == "L" else slice(int(w * 0.85), w)
        prof = gy[:, cols].mean(axis=1)
        prof[: int(h * 0.03)] = 0
        prof[int(h * 0.97):] = 0
        best = None
        for row in np.argsort(prof)[::-1][:12]:
            x = run_from_edge(int(row), side)
            length = x if side == "L" else (w - 1 - x)
            if best is None or length > best[2]:
                best = (int(row), x, length)
        return best[0], best[1]

    lr, lx = tip("L")
    rr, rx = tip("R")
    if rx - lx < w * 0.2:
        raise ValueError("platform tips not found or too close together")
    return GapScale(left_tip_px=float(lx), right_tip_px=float(rx), left_row=lr, right_row=rr)
