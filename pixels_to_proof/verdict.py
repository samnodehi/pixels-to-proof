"""Verdict rule: transparent and deterministic, so a reader can redo it by hand."""
from __future__ import annotations

from dataclasses import asdict, dataclass

REPRODUCED = "REPRODUCED"
NOT_REPRODUCED = "NOT REPRODUCED"
CANNOT_MEASURE = "CANNOT MEASURE"

G_TOLERANCE = 0.10   # the fitted free-fall acceleration must be within 10% of 9.81 m/s^2


@dataclass
class Verdict:
    label: str
    published: float
    published_unc: float | None
    measured_mid: float
    measured_lo: float
    measured_hi: float
    rel_diff: float          # (published - measured_mid) / measured_mid
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def decide(published: float, published_unc: float | None, mid: float, lo: float, hi: float,
           g_rel_err: float | None) -> Verdict:
    rel = (published - mid) / mid
    if g_rel_err is not None and abs(g_rel_err) > G_TOLERANCE:
        return Verdict(CANNOT_MEASURE, published, published_unc, mid, lo, hi, rel,
                       f"self-check failed: gravity from the flight is {g_rel_err:+.0%} off 9.81 m/s^2, "
                       "so scale or frame rate is wrong")
    p_lo = published - (published_unc or 0.0)
    p_hi = published + (published_unc or 0.0)
    if p_hi >= lo and p_lo <= hi:
        return Verdict(REPRODUCED, published, published_unc, mid, lo, hi, rel,
                       "published value (with its stated uncertainty) overlaps the measured interval")
    return Verdict(NOT_REPRODUCED, published, published_unc, mid, lo, hi, rel,
                   "published value lies outside the measured interval")
