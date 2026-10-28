"""Blind pairing: which row of the paper's event table is the jump in this video? Only trajectory geometry is
compared (take-off angle, distance, height, airborne time); the published speed is never looked at, so the choice
cannot be steered by the value being checked."""
from __future__ import annotations

import math

import numpy as np

from .ingest import Table
from .measure import Kinematics

def _mirror(k: Kinematics) -> tuple[float, float]:
    """Tables report jumps as positive distance and angle; a jump filmed right-to-left is mirrored."""
    if k.distance_mm < 0:
        return 180.0 - k.angle_deg, -k.distance_mm
    return k.angle_deg, k.distance_mm


FEATURE_FROM_K = {
    "takeoff_angle": lambda k: _mirror(k)[0],
    "jump_distance": lambda k: _mirror(k)[1] / 1000.0,
    "jump_height": lambda k: k.height_mm / 1000.0,
    "end_height": lambda k: k.end_height_mm / 1000.0,
    "airborne_time": lambda k: k.airborne_s,
}


def pair(k: Kinematics, table: Table, columns: dict[str, dict], id_column: str | None, min_margin: float) -> dict:
    """Rank all rows by z-scored distance over the available trajectory features. Each feature quantity counts once
    (columns of the same quantity are averaged). Accepted only if the best row is min_margin times closer than the
    second best."""
    feats: dict[str, list[tuple[str, int, float]]] = {}
    for name, c in columns.items():
        if c["quantity"] in FEATURE_FROM_K and c.get("si_factor"):
            feats.setdefault(c["quantity"], []).append((name, c["index"], c["si_factor"]))
    if len(feats) < 2:
        return {"ok": False, "reason": f"only {len(feats)} trajectory quantities in the table; at least 2 needed"}
    ours = {q: FEATURE_FROM_K[q](k) for q in feats}
    scores = []
    for i, r in enumerate(table.rows):
        per_q = []
        for q, cols in feats.items():
            zs = []
            for name, j, fac in cols:
                col = [row[j] * fac for row in table.rows if _num(row[j])]
                sd = float(np.std(col, ddof=1)) if len(col) > 2 else 0.0
                if _num(r[j]) and sd > 0:
                    zs.append(abs(ours[q] - r[j] * fac) / sd)
            if zs:
                per_q.append(float(np.mean(zs)))
        if len(per_q) >= 2:
            scores.append((math.sqrt(float(np.mean(np.square(per_q)))), i, len(per_q)))
    if len(scores) < 2:
        return {"ok": False, "reason": "fewer than two table rows carry the trajectory quantities"}
    scores.sort()
    (d1, i1, _), (d2, i2, _) = scores[0], scores[1]
    margin = d2 / d1 if d1 > 0 else float("inf")
    idx = table.header.index(id_column) if id_column in table.header else None
    # an event id that repeats across animals ("j1", "j2" per spider) is prefixed with the animal id when there is one
    animal = next((c["index"] for c in columns.values() if c.get("quantity") == "animal_id"), None)
    ids = [table.rows[i][idx] for i in range(len(table.rows))] if idx is not None else []
    unique = len(set(map(str, ids))) == len(ids)

    def rid(i: int) -> str:
        if idx is None:
            return f"row {i + 1}"
        if unique or animal is None:
            return str(table.rows[i][idx])
        return f"{table.rows[i][animal]}/{table.rows[i][idx]}"
    detail = {q: {"ours": ours[q], "row": {name: (table.rows[i1][j] * fac if _num(table.rows[i1][j]) else None)
                                           for name, j, fac in cols}} for q, cols in feats.items()}
    out = {"row_index": i1, "row_id": rid(i1), "distance": d1, "runner_up": rid(i2), "runner_up_distance": d2,
           "margin": margin, "features": sorted(feats), "n_rows": len(scores), "detail": detail,
           "top3": [(rid(i), round(d, 3)) for d, i, _ in scores[:3]]}
    if margin < min_margin:
        return {**out, "ok": False, "reason": f"best row {rid(i1)} is only {margin:.2f}x closer than {rid(i2)} "
                                              f"(needs {min_margin}x): not unambiguous"}
    return {**out, "ok": True, "reason": f"{rid(i1)} is {margin:.1f}x closer than the runner-up {rid(i2)}"}


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and not (isinstance(v, float) and math.isnan(v))
