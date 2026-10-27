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
