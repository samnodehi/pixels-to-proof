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


def _per_animal(claim: dict, col: dict, table: Table, columns: dict[str, dict], conv: float) -> tuple[list, str] | None:
    """When a claim states its n and that n is not the number of rows, it may be a statistic over animals: each animal's
    rows are averaged first. The animal is the animal-id column, alone or together with one categorical column (IDs
    are often reused across conditions); a grouping is used only if it yields exactly the stated n."""
    n = claim.get("n_events")
    ids = [c for c in columns.values() if c.get("quantity") == "animal_id" and c["name"] in table.header]
    if not n or not ids:
        return None
    rows = _rows(claim, table)
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    rf = (claim.get("row_filter") or {}).get("column")
    cats = [h for j, h in enumerate(table.header)
            if h not in (rf, ids[0]["name"]) and rows and not any(num(r[j]) for r in rows)
            and columns.get(h, {}).get("quantity") != "event_id"]
    a = table.header.index(ids[0]["name"])
    for extra in [None] + cats:
        e = table.header.index(extra) if extra else None
        groups: dict = {}
        for r in rows:
            if num(r[col["index"]]):
                groups.setdefault((r[a], r[e] if e is not None else None), []).append(r[col["index"]] * conv)
        if len(groups) == n:
            key = ids[0]["name"] + (f" + {extra}" if extra else "")
            return [statistics.fmean(v) for v in groups.values()], key
    return None


def _try(claim: dict, col: dict, table: Table, circular: bool = False, columns: dict | None = None) -> dict:
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
    if not out["ok"] and claim["statistic"] == "mean" and claim.get("plus_minus") is not None and len(vals) > 1 \
            and abs(centre - claim["value"]) <= _tol(vt, vs):
        psd = statistics.pstdev(vals)                  # some papers print the population SD (divide by n, not n-1)
        if judge(centre, psd):
            out.update(ok=True, table_sd=psd, stats="population_sd")
    if not out["ok"] and circular and claim["statistic"] == "mean" and unit_dim(col["unit"]) == "angle":
        c_mean, c_sd = _circular(vals)
        if judge(c_mean, c_sd):
            out.update(ok=True, table_value=c_mean, table_sd=c_sd, stats="circular")
    if not out["ok"] and claim["statistic"] == "mean" and claim.get("n_events") and claim["n_events"] != len(vals):
        pa = _per_animal(claim, col, table, columns or {}, conv)
        if pa:
            means, key = pa
            c, sd = _stats(means, "mean")
            out.update(per_animal={"groups": len(means), "key": key, "value": c, "sd": sd})
            if judge(c, sd):
                out.update(ok=True, table_value=c, table_sd=sd, stats="per_animal", n_rows=len(means))
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
        r = _try(claim, named, table, circular, columns)
        tried.append(r)
        if r["ok"]:
            rows = "" if r.get("stats") == "per_animal" else f"{r['n_rows']} rows of "
            return {**r, "outcome": MATCHES, "reason": f"{_how(claim, r)} of {rows}'{r['column']}'"
                                                       f"{_subset(claim)} reproduces the printed digits"}
    for name, col in columns.items():
        if col is named or unit_dim(col["unit"]) != dim:
            continue
        r = _try(claim, col, table, circular, columns)
        if r["ok"]:
            return {**r, "outcome": OTHER_COLUMN, "proposed_column": claim.get("table_column"),
                    "proposed_quantity": claim["quantity"], "column_quantity": col["quantity"],
                    "reason": f"'{name}' ({col['quantity']}) reproduces the printed digits; the column proposed for this "
                              f"sentence ('{claim.get('table_column')}') does not"}
    # The statistic is Spark's proposal too ("maximum acceleration" can be the mean of per-jump maxima). If the proposed
    # one fails on the named column, the others are tried there, only for values printed with >= 3 significant digits.
    if named is not None and unit_dim(named["unit"]) == dim and claim["statistic"] in ("mean", "median", "max", "min") \
            and len(re.sub(r"[^0-9]", "", (_printed(claim["value"], claim["quote"])[0] or "")).lstrip("0")) >= 3:
        for stat in ("mean", "median", "max", "min"):
            if stat == claim["statistic"] or (stat != "mean" and claim.get("plus_minus") is not None):
                continue
            r = _try(dict(claim, statistic=stat), named, table, circular, columns)
            if r["ok"]:
                return {**r, "outcome": MATCHES, "statistic_used": stat,
                        "reason": f"the {stat} (not the proposed {claim['statistic']}) of {r['n_rows']} rows of "
                                  f"'{r['column']}'{_subset(claim)} reproduces the printed digits"}
    # The subset is Spark's proposal too. If no subset was proposed and all rows fail, each group of a grouping column
    # (2–6 distinct values) is tried on the named column; a mean needs its ± to match as well, a single value needs
    # >= 3 significant digits.
    rf = claim.get("row_filter") or {}
    sig = len(re.sub(r"[^0-9]", "", (_printed(claim["value"], claim["quote"])[0] or "")).lstrip("0"))
    # Only when the whole column's own centre already misses the printed value: subsets of one population have
    # similar means, so a subset could otherwise "match" a value that describes all rows.
    whole = tried[0] if tried and "table_value" in tried[0] else None
    vt0, vs0 = _printed(claim["value"], claim["quote"])
    centre_misses = whole is not None and abs(whole["table_value"] - claim["value"]) > _tol(vt0, vs0)
    if named is not None and unit_dim(named["unit"]) == dim and not rf.get("column") and centre_misses and \
            (claim.get("plus_minus") is not None or sig >= 3):
        for h, vals in _groupings(table).items():
            for v in vals:
                r = _try(dict(claim, row_filter={"column": h, "value": v}), named, table, circular, columns)
                if r["ok"]:
                    return {**r, "outcome": MATCHES, "subset_found_by_code": {"column": h, "value": v},
                            "reason": f"{_how(claim, r)} of {r['n_rows']} rows of '{r['column']}' (rows where {h} = "
                                      f"{v}; the plan named no subset, code found it) reproduces the printed digits"}
    if tried and "table_value" in tried[0]:
        r = tried[0]
        shown = f"{r['table_value']:.4g}" + (f" ± {r['table_sd']:.3g}" if r["table_sd"] is not None and
                                             claim.get("plus_minus") is not None else "")
        vt, vs = _printed(claim["value"], claim["quote"])
        pt, ps = _printed(claim["plus_minus"], claim["quote"]) if claim.get("plus_minus") is not None else (None, 1.0)
        if vt is not None and claim.get("plus_minus") is not None and pt is not None and r.get("table_sd") is not None \
                and claim["statistic"] == "mean":
            d, e = (len(x.split(".")[1]) if "." in x else 0 for x in (vt, pt))
            q, qe = 10 ** d / vs, 10 ** e / ps
            tv, ts = r["table_value"], r["table_sd"]
            if math.trunc(tv * q) == round(claim["value"] * q) and math.trunc(ts * qe) == round(claim["plus_minus"] * qe):
                return {**r, "outcome": NOT_CHECKED,
                        "reason": f"'{r['column']}' over {r['n_rows']} rows{_subset(claim)} gives {tv:.{d + 2}f} ± "
                                  f"{ts:.{e + 2}f}: the printed values are these truncated, not rounded"}
        if vt is not None and claim.get("plus_minus") is None:
            d = len(vt.split(".")[1]) if "." in vt else 0
            q = 10 ** d / vs
            for stat in [claim["statistic"]] + [x for x in ("mean", "median", "max", "min") if x != claim["statistic"]]:
                rr = r if stat == claim["statistic"] else _try(dict(claim, statistic=stat), named, table, circular,
                                                               columns)
                tv = rr.get("table_value")
                if tv is not None and math.trunc(tv * q) == round(claim["value"] * q) and \
                        abs(tv - claim["value"]) < 1 / q:
                    return {**rr, "outcome": NOT_CHECKED,
                            "reason": f"the {stat} of '{rr['column']}' over {rr['n_rows']} rows{_subset(claim)} is "
                                      f"{tv:.{d + 2}f}: the printed {vt} is that value truncated, not rounded"}
        pa = r.get("per_animal")
        extra = (f"; averaged per animal ({pa['groups']} animals, the n printed) it gives {pa['value']:.4g}"
                 + (f" ± {pa['sd']:.3g}" if pa["sd"] is not None and claim.get("plus_minus") is not None else "")
                 if pa else "")
        return {**r, "outcome": NOT_CHECKED,
                "reason": f"no column reproduces the printed digits{extra}; '{r['column']}' over {r['n_rows']} rows"
                          f"{_subset(claim)} gives "
                          f"{shown} {claim['unit']} (the printed value may use another aggregation unit)"}
    return {"outcome": NOT_CHECKED, "reason": "no column of this dimension reproduces the printed digits"}


def _how(claim: dict, r: dict) -> str:
    if r.get("stats") == "circular":
        return "circular mean (the paper uses circular statistics)"
    if r.get("stats") == "population_sd":
        return "mean with the population SD (divided by n, not n − 1)"
    if r.get("stats") == "per_animal":
        return (f"mean over animals (each animal's rows averaged first; animal = {r['per_animal']['key']}; "
                f"{r['per_animal']['groups']} animals = the n printed)")
    return claim["statistic"]


def _subset(claim: dict) -> str:
    rf = claim.get("row_filter") or {}
    return f" (rows where {rf['column']} = {rf['value']})" if rf.get("column") else ""


def _groupings(table: Table, max_groups: int = 6) -> dict[str, list]:
    """Columns that look like group labels: 2..max_groups distinct values, each shared by at least two rows."""
    out = {}
    for j, h in enumerate(table.header):
        vals = [r[j] for r in table.rows if r[j] is not None and str(r[j]).strip() != ""]
        distinct = sorted({str(v).strip() for v in vals})
        if 2 <= len(distinct) <= max_groups and len(vals) >= 2 * len(distinct):
            out[h] = distinct
    return out
