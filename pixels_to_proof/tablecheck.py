"""TABLE CHECK: an aggregate claim (mean ± SD, max, ...) recomputed from the paper's own event table. Arithmetic only,
no model. Outcomes: MATCHES TABLE, or NOT CHECKED with the values the table gives (never a judgement of the paper:
the aggregation unit or column behind a printed number is not always stated)."""
from __future__ import annotations

import math
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
    q = re.sub(r"(\d*\.?\d+)[eE]([-+]?\d+)", lambda m: f"{m.group(1)} x 10-{-int(m.group(2))}"
               if int(m.group(2)) < 0 else m.group(0), q)          # '1.2e-3' printed as '1.2 x 10-3'
    m = re.search(r"[x×]\s*10\s*[-−–]\s*(\d+)", q)
    k = 10 ** -int(m.group(1)) if m else 1.0
    for tok in re.findall(r"(?<![\d.])\d*\.?\d+", q):
        for scale in ((k, 1.0) if k != 1.0 else (1.0,)):
            if abs(float(tok) * scale - value) <= 1e-12 + 1e-6 * abs(value):
                return tok, scale
    return None, 1.0


def _tol(tok: str | None, scale: float) -> float:
    """Half a unit of the last printed digit. Without the printed token there is no tolerance: no match."""
    if tok is None:
        return -1.0
    d = len(tok.split(".")[1]) if "." in tok else 0
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


def _circular(vals_deg: list[float]) -> tuple[float, float]:
    """Circular mean and circular standard deviation sqrt(-2 ln R) of angles in degrees."""
    a = [math.radians(v) for v in vals_deg]
    c, s = sum(map(math.cos, a)) / len(a), sum(map(math.sin, a)) / len(a)
    r = math.hypot(c, s)
    return math.degrees(math.atan2(s, c)), math.degrees(math.sqrt(-2 * math.log(r))) if 0 < r < 1 else 0.0


def _rows(claim: dict, table: Table) -> list:
    rf = claim.get("row_filter") or {}
    if not rf.get("column") or rf["column"] not in table.header:
        return table.rows
    j = table.header.index(rf["column"])
    return [r for r in table.rows if str(r[j]).strip().lower() == str(rf.get("value")).strip().lower()]


def _try(claim: dict, col: dict, table: Table, circular: bool = False) -> dict:
    cf, kf = col.get("si_factor"), claim.get("si_factor")
    conv = (cf / kf) if (cf is not None and kf is not None) else 1.0      # column value -> claim unit
    vals = [r[col["index"]] * conv for r in _rows(claim, table)
            if isinstance(r[col["index"]], (int, float)) and not isinstance(r[col["index"]], bool)]
    if len(vals) < 2:
        return {"ok": False, "column": col["name"], "reason": "fewer than two numeric rows"}
    vt, vs = _printed(claim["value"], claim["quote"])
    pt, ps = _printed(claim["plus_minus"], claim["quote"]) if claim.get("plus_minus") is not None else (None, 1.0)

    def judge(centre, sd):
        ok = abs(centre - claim["value"]) <= _tol(vt, vs)
        if claim.get("plus_minus") is not None and claim["statistic"] == "mean":
            ok = ok and sd is not None and abs(sd - claim["plus_minus"]) <= _tol(pt, ps)
        return ok

    centre, sd = _stats(vals, claim["statistic"])
    out = {"ok": judge(centre, sd), "column": col["name"], "n_rows": len(vals), "table_value": centre,
           "table_sd": sd, "stats": "arithmetic"}
    if not out["ok"] and circular and claim["statistic"] == "mean" and unit_dim(col["unit"]) == "angle":
        c_mean, c_sd = _circular(vals)
        if judge(c_mean, c_sd):
            out.update(ok=True, table_value=c_mean, table_sd=c_sd, stats="circular")
    return out


def check(claim: dict, table: Table, columns: dict[str, dict], circular: bool = False) -> dict:
    """Recompute the claim from the column the plan named; if that fails, scan every other column of the same
    dimension and report a match there as MATCHES OTHER COLUMN (the plan's column choice was wrong, or the printed
    sentence describes the quantity differently than the column does)."""
    if claim["statistic"] == "mean" and claim.get("plus_minus") is not None and claim.get("spread") != "sd":
        return {"outcome": NOT_CHECKED, "reason": f"spread type '{claim.get('spread')}' is not a standard deviation"}
    dim = unit_dim(claim["unit"])
    named = columns.get(claim.get("table_column") or "")
    tried = []
    if named is not None and unit_dim(named["unit"]) == dim:
        r = _try(claim, named, table, circular)
        tried.append(r)
        if r["ok"]:
            return {**r, "outcome": MATCHES, "reason": f"{_how(claim, r)} of {r['n_rows']} rows of '{r['column']}'"
                                                       f"{_subset(claim)} reproduces the printed digits"}
    for name, col in columns.items():
        if col is named or unit_dim(col["unit"]) != dim:
            continue
        r = _try(claim, col, table, circular)
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
                "reason": f"no column reproduces the printed digits; '{r['column']}' over {r['n_rows']} rows"
                          f"{_subset(claim)} gives "
                          f"{shown} {claim['unit']} (the printed value may use another aggregation unit)"}
    return {"outcome": NOT_CHECKED, "reason": "no column of this dimension reproduces the printed digits"}


def _how(claim: dict, r: dict) -> str:
    return ("circular mean (the paper uses circular statistics)" if r.get("stats") == "circular"
            else claim["statistic"])


def _subset(claim: dict) -> str:
    rf = claim.get("row_filter") or {}
    return f" (rows where {rf['column']} = {rf['value']})" if rf.get("column") else ""
