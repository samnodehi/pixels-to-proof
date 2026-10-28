"""TABLE CHECK: an aggregate claim (mean ± SD, max, ...) recomputed from the paper's own event table. Arithmetic only,
no model. Outcomes: MATCHES TABLE, or NOT CHECKED with the values the table gives (never a judgement of the paper:
the aggregation unit or column behind a printed number is not always stated)."""
from __future__ import annotations

import re
import statistics

from .ingest import Table
from .plan import unit_dim

MATCHES = "MATCHES TABLE"
OTHER_COLUMN = "MATCHES OTHER COLUMN"
NOT_CHECKED = "NOT CHECKED"


def _printed(value: float, quote: str) -> tuple[str | None, float]:
    """The token in the quote that prints this value, and the power of ten applied to it ('x 10-3')."""
    q = quote.replace(",", "")
    m = re.search(r"[x×]\s*10\s*[-−–]\s*(\d+)", q)
    k = 10 ** -int(m.group(1)) if m else 1.0
    for tok in re.findall(r"(?<![\d.])\d*\.?\d+", q):
        for scale in ((k, 1.0) if k != 1.0 else (1.0,)):
            if abs(float(tok) * scale - value) <= 1e-12 + 1e-6 * abs(value):
                return tok, scale
    return None, 1.0


def _tol(tok: str | None, scale: float) -> float:
    d = len(tok.split(".")[1]) if tok and "." in tok else 0
    return 0.5 * 10 ** -d * scale + 1e-12


def _stats(vals: list[float], statistic: str) -> tuple[float, float | None]:
    if statistic == "mean":
        return statistics.fmean(vals), (statistics.stdev(vals) if len(vals) > 1 else None)
    if statistic == "median":
        return statistics.median(vals), None
    if statistic == "max":
        return max(vals), None
    if statistic == "min":
        return min(vals), None
    raise ValueError(statistic)


def _try(claim: dict, col: dict, table: Table) -> dict:
    cf, kf = col.get("si_factor"), claim.get("si_factor")
    conv = (cf / kf) if (cf is not None and kf is not None) else 1.0      # column value -> claim unit
    vals = [r[col["index"]] * conv for r in table.rows
            if isinstance(r[col["index"]], (int, float)) and not isinstance(r[col["index"]], bool)]
    if len(vals) < 2:
        return {"ok": False, "column": col["name"], "reason": "fewer than two numeric rows"}
    centre, sd = _stats(vals, claim["statistic"])
    vt, vs = _printed(claim["value"], claim["quote"])
    ok = abs(centre - claim["value"]) <= _tol(vt, vs)
    if claim.get("plus_minus") is not None and claim["statistic"] == "mean":
        pt, ps = _printed(claim["plus_minus"], claim["quote"])
        ok = ok and sd is not None and abs(sd - claim["plus_minus"]) <= _tol(pt, ps)
    return {"ok": ok, "column": col["name"], "n_rows": len(vals), "table_value": centre, "table_sd": sd}


def check(claim: dict, table: Table, columns: dict[str, dict]) -> dict:
    """Recompute the claim from the column the plan named; if that fails, scan every other column of the same
    dimension and report a match there as MATCHES OTHER COLUMN (the plan's column choice was wrong, or the printed
    sentence describes the quantity differently than the column does)."""
    if claim["statistic"] == "mean" and claim.get("plus_minus") is not None and claim.get("spread") != "sd":
        return {"outcome": NOT_CHECKED, "reason": f"spread type '{claim.get('spread')}' is not a standard deviation"}
    dim = unit_dim(claim["unit"])
    named = columns.get(claim.get("table_column") or "")
    tried = []
    if named is not None and unit_dim(named["unit"]) == dim:
        r = _try(claim, named, table)
        tried.append(r)
        if r["ok"]:
            return {**r, "outcome": MATCHES, "reason": f"{claim['statistic']} of {r['n_rows']} rows of '{r['column']}' "
                                                       "reproduces the printed digits"}
    for name, col in columns.items():
        if col is named or unit_dim(col["unit"]) != dim:
            continue
        r = _try(claim, col, table)
        if r["ok"]:
            return {**r, "outcome": OTHER_COLUMN, "proposed_column": claim.get("table_column"),
                    "proposed_quantity": claim["quantity"], "column_quantity": col["quantity"],
                    "reason": f"'{name}' ({col['quantity']}) reproduces the printed digits; the column proposed for this "
                              f"sentence ('{claim.get('table_column')}') does not"}
    if tried and "table_value" in tried[0]:
        r = tried[0]
        shown = f"{r['table_value']:.4g}" + (f" ± {r['table_sd']:.3g}" if r["table_sd"] is not None and
                                             claim.get("plus_minus") is not None else "")
        return {**r, "outcome": NOT_CHECKED,
                "reason": f"no column reproduces the printed digits; '{r['column']}' over {r['n_rows']} rows gives "
                          f"{shown} {claim['unit']} (the printed value may use another aggregation unit)"}
    return {"outcome": NOT_CHECKED, "reason": "no column of this dimension reproduces the printed digits"}
