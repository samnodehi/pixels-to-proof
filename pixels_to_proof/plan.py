"""The audit plan: Muse Spark reads the paper, its tables, its analysis scripts and the video inventory and proposes
what each file and column is, which claims exist and how the authors measured speed. Code then checks every field
(gate G1). Nothing here produces a measured number."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import ingest, meta, read

# Fine-grained on purpose: pairing a video jump to a table row may only use the trajectory quantities.
QUANTITIES = ["takeoff_speed", "speed_uncertainty", "takeoff_angle", "jump_distance", "jump_height", "airborne_time",
              "body_angle", "other_angle", "other_length", "other_duration", "other_speed", "body_length", "mass",
              "frame_index", "event_id", "animal_id", "acceleration", "other"]
QUANTITY_HELP = ("takeoff_speed = speed of the body at take-off; takeoff_angle = direction of the trajectory at take-off "
                 "(NOT a body posture angle); jump_distance = horizontal distance covered in the jump; jump_height = "
                 "maximum height of the jump; airborne_time = time in the air; body_angle = posture or bending angle; "
                 "other_* = any other quantity of that kind (e.g. displacement during loading).")
PAIRING = {"takeoff_angle", "jump_distance", "jump_height", "airborne_time"}
SI = {"takeoff_speed", "takeoff_angle", "jump_distance", "jump_height", "airborne_time", "other_duration",
      "other_length", "other_speed", "acceleration", "body_angle", "other_angle", "body_length"}

_COLUMN = {"type": "object", "additionalProperties": False,
           "properties": {
               "name": {"type": "string", "description": "column header exactly as in the table digest"},
               "quantity": {"type": "string", "enum": QUANTITIES, "description": QUANTITY_HELP},
               "unit": {"type": "string", "description": "unit of the stored values, e.g. m/s, m, mm, s, ms, deg; 'ratio' if dimensionless or relative; '' if not a quantity"},
               "uncertainty_of": {"type": ["string", "null"], "description": "for an uncertainty column: the header of the column it belongs to"},
               "uncertainty_kind": {"type": "string", "enum": ["absolute", "relative", "not_an_uncertainty", "unknown"]},
               "evidence": {"type": "string", "description": "exact quote from the paper text or the script that supports unit/meaning, or '' if none"}},
           "required": ["name", "quantity", "unit", "uncertainty_of", "uncertainty_kind", "evidence"]}

PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "videos": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "file": {"type": "string", "description": "file name from the inventory"},
                "label": {"type": "string", "description": "how the paper calls it, e.g. 'S2 Video'"},
                "capture_fps": {"type": ["number", "null"]},
                "fps_evidence": {"type": "string", "description": "exact quote (paper or overlay text) stating the capture rate, or ''"},
                "content": {"type": "string"}},
            "required": ["file", "label", "capture_fps", "fps_evidence", "content"]}},
        "event_table": {"type": ["object", "null"], "additionalProperties": False,
                        "description": "the table in which each row is ONE recorded event (one jump), if any",
                        "properties": {
                            "file": {"type": "string"}, "sheet": {"type": "string"},
                            "rows_are": {"type": "string"},
                            "columns": {"type": "array", "items": _COLUMN}},
                        "required": ["file", "sheet", "rows_are", "columns"]},
        "scale_reference": {"type": "object", "additionalProperties": False,
                            "properties": {
                                "kind": {"type": "string", "enum": ["grid", "platform_gap", "scale_bar", "ruler", "none"]},
                                "size_mm": {"type": ["number", "null"]},
                                "evidence": {"type": "string"}},
                            "required": ["kind", "size_mm", "evidence"]},
        "object_phrase": {"type": "string", "description": "1-3 word noun phrase naming the moving animal/object for a segmentation model"},
        "authors_speed_method": {"type": "object", "additionalProperties": False,
                                 "properties": {
                                     "family": {"type": "string", "enum": ["ballistic_fit", "smoothing_spline_max",
                                                                           "finite_difference", "linear_fit", "other", "unknown"]},
                                     "parameters": {"type": "string", "description": "e.g. 'smooth.Pspline spar=1e-8 method=1, whole track, max of derivative'"},
                                     "evidence": {"type": "string", "description": "exact quote from paper or script"}},
                                 "required": ["family", "parameters", "evidence"]},
        "claims": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "quantity": {"type": "string", "enum": QUANTITIES, "description": QUANTITY_HELP},
                "value": {"type": "number"},
                "plus_minus": {"type": ["number", "null"]},
                "unit": {"type": "string"},
                "quote": {"type": "string", "description": "exact sentence fragment from the PDF containing the number"},
                "statistic": {"type": "string", "enum": ["mean", "median", "max", "min", "single_event", "other"]},
                "spread": {"type": "string", "enum": ["sd", "se", "range", "ci", "none", "unknown"]},
                "n_events": {"type": ["integer", "null"], "description": "number of events the value aggregates, if stated"},
                "table_column": {"type": ["string", "null"], "description": "event_table column this claim summarises, if any"}},
            "required": ["quantity", "value", "plus_minus", "unit", "quote", "statistic", "spread", "n_events", "table_column"]}}},
    "required": ["title", "videos", "event_table", "scale_reference", "object_phrase", "authors_speed_method", "claims"]}

PLAN_PROMPT = """You are planning an audit of the kinematic numbers in a scientific paper against its own supplementary
material. Below: an inventory of the files, a text digest of every table, the text of analysis scripts shipped with the
paper, and what is printed on the videos. The PDF is attached.

Propose, strictly from what the material says:
- each video: its label in the paper, its capture frame rate with the exact quote that states it, and what it shows;
- the table in which each row is one recorded event (one jump), with the meaning and unit of EVERY column. For any
  column that is an uncertainty, say which column it belongs to and whether it is absolute or relative, with an exact
  quote (paper sentence or script line) that shows it; if nothing shows it, use 'unknown';
- the spatial scale reference visible in the videos and its real size, with the quote;
- a noun phrase for the moving animal;
- how the authors computed speed (method family and parameters) with an exact quote from the paper or script;
- every quantitative kinematic claim in the PDF (speeds, distances, heights, durations, angles, accelerations):
  value, ±, unit, an exact quote, whether it is a single event or a statistic over events (mean, max, ...), the spread
  type, n if stated, and which event-table column it summarises if any.
Do not invent anything. Quotes must be copied exactly from one contiguous passage; to cite two separate passages,
join them with ' ... '. Use null or 'unknown' where the material is silent.

FILE INVENTORY
{inventory}

TABLES
{tables}

SCRIPTS
{scripts}

VIDEO INVENTORY (shots found by cut detection; text printed on a frame of each shot)
{videos}
"""


@dataclass
class Check:
    field: str
    ok: bool
    note: str


@dataclass
class CheckedPlan:
    plan: dict
    checks: list[Check] = field(default_factory=list)
    columns: dict[str, dict] = field(default_factory=dict)     # accepted event-table columns by header
    claims: list[dict] = field(default_factory=list)           # claims that passed G1, with 'checked' notes

    def rejected(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]


def make_plan(pdf: Path, inventory_text: str, tables_text: str, scripts_text: str, videos_text: str,
              feedback: str = "", file_id: str | None = None) -> tuple[dict, dict, str]:
    """One plan proposal. `feedback` lists the fields a checker rejected in the previous proposal (re-proposal)."""
    fid = file_id or meta.upload(pdf, "application/pdf")
    prompt = PLAN_PROMPT.format(inventory=inventory_text, tables=tables_text, scripts=scripts_text or "(none)",
                                videos=videos_text)
    if feedback:
        prompt += ("\n\nAN AUTOMATIC CHECKER REJECTED THESE FIELDS OF YOUR PREVIOUS PROPOSAL (it verifies every quote "
                   "against the files, every unit and every value range):\n" + feedback +
                   "\nReturn the complete plan again. Fix only what was rejected, using quotes copied exactly; if the "
                   "material does not support a field, say 'unknown' or null instead.")
    plan, usage = read._structured([{"type": "input_file", "file_id": fid}, {"type": "input_text", "text": prompt}],
                                   "audit_plan", PLAN_SCHEMA)
    return plan, usage, fid


CRITICAL = ("fps", "kind", "scale size", "authors' method", "claim '")


def merge(old: dict, new: dict, rejected: list[Check]) -> dict:
    """Take from a re-proposal only the fields the checker rejected in the previous version; everything that already
    passed stays as it was (a re-proposal must not silently change accepted fields)."""
    import copy
    out = copy.deepcopy(old)
    names = " | ".join(c.field for c in rejected)
    if "authors' method" in names:
        out["authors_speed_method"] = new["authors_speed_method"]
    if "scale size" in names and new["scale_reference"].get("kind") == out["scale_reference"].get("kind"):
        out["scale_reference"] = dict(out["scale_reference"], size_mm=new["scale_reference"]["size_mm"],
                                      evidence=new["scale_reference"]["evidence"])
    for v in out.get("videos", []):
        if f"video {v['file']} fps" in names:
            alt = [w for w in new.get("videos", []) if w["file"] == v["file"] and w.get("label") == v.get("label")]
            if alt:
                v.update(alt[0])
    if out.get("event_table") and new.get("event_table"):
        newcols = {c["name"]: c for c in new["event_table"]["columns"]}
        for i, c in enumerate(out["event_table"]["columns"]):
            if f"column {c['name']} kind" in names and c["name"] in newcols:
                out["event_table"]["columns"][i] = newcols[c["name"]]
    bad = [c.field[len("claim '"):-1] for c in rejected if c.field.startswith("claim '")]
    keep, repl = [], []
    for cl in out.get("claims", []):
        if any(cl["quote"][:50] == b for b in bad):
            alt = [x for x in new.get("claims", []) if x["quantity"] == cl["quantity"]
                   and abs(x["value"] - cl["value"]) <= 1e-9 + 1e-6 * abs(cl["value"])]
            repl += alt[:1]
        else:
            keep.append(cl)
    out["claims"] = keep + repl
    return out


def feedback_for(cp: "CheckedPlan") -> str:
    """The rejections worth a re-proposal: those that drop a field the audit needs (not 'unit not absolute')."""
    lines = [f"- {c.field}: {c.note}" for c in cp.rejected() if any(k in c.field for k in CRITICAL)]
    return "\n".join(lines)


_UNIT_SCALE = {"m/s": 1.0, "m s-1": 1.0, "ms-1": 1.0, "m/sec": 1.0, "mm/s": 1e-3, "cm/s": 1e-2,
               "m": 1.0, "mm": 1e-3, "cm": 1e-2, "um": 1e-6, "µm": 1e-6,
               "s": 1.0, "ms": 1e-3, "sec": 1.0, "deg": 1.0, "degree": 1.0, "degrees": 1.0, "°": 1.0,
               "m/s2": 1.0, "m/s^2": 1.0, "m s-2": 1.0, "m/sec2": 1.0}


_DIM = {"m/s": "speed", "m s-1": "speed", "ms-1": "speed", "m/sec": "speed", "mm/s": "speed", "cm/s": "speed",
        "m": "length", "mm": "length", "cm": "length", "um": "length", "µm": "length",
        "s": "time", "ms": "time", "sec": "time", "deg": "angle", "degree": "angle", "degrees": "angle", "°": "angle",
        "m/s2": "accel", "m/s^2": "accel", "m s-2": "accel", "m/sec2": "accel"}


_MULT = re.compile(r"^\s*[x×*]?\s*10\s*(?:\^|e)?\s*\(?([-−–]?\d+)\)?\s*")


def _split_multiplier(unit: str) -> tuple[float, str]:
    """'x 10-3 s' -> (1e-3, 's'): a printed power of ten in front of the unit."""
    m = _MULT.match(unit)
    if m and unit[m.end():].strip():
        return 10.0 ** int(m.group(1).replace("−", "-").replace("–", "-")), unit[m.end():]
    return 1.0, unit


def unit_dim(unit: str) -> str:
    """Physical dimension of a unit, or the unit text itself when it is not an absolute unit."""
    unit = _split_multiplier(unit)[1]
    u = unit.strip().lower().replace("²", "2").replace(" ", "")
    for k, v in _DIM.items():
        if u == k.replace(" ", ""):
            return v
    if u.replace("_", "").replace("-", "") in {"ratio", "relative", "bodylengths", "bodylength", "bl", "dimensionless",
                                                "bodylengthunits", ""}:
        return "ratio"
    return "other:" + u


def unit_factor(unit: str) -> float | None:
    mult, unit = _split_multiplier(unit)
    u = unit.strip().lower().replace("²", "2").replace(" ", "")
    for k, v in _UNIT_SCALE.items():
        if u == k.replace(" ", ""):
            return v * mult
    return None


def check(plan: dict, pdf_text: str, script_text: str, tables: list[ingest.Table], overlay_text: str) -> CheckedPlan:
    """Gate G1: every field Spark proposed is checked against the files; failing fields are dropped, not repaired."""
    cp = CheckedPlan(plan=plan)
    corpus = ingest.normalise(pdf_text + "\n" + script_text + "\n" + overlay_text)

    def quoted(q: str) -> bool:
        return bool(q) and ingest.quote_in_text(q, corpus, min_len=8)

    for v in plan.get("videos", []):
        q = v.get("fps_evidence", "")
        ok = v.get("capture_fps") is None or (quoted(q) and _number_in(float(v["capture_fps"]), q))
        cp.checks.append(Check(f"video {v['file']} fps", ok,
                               "fps quote found and states the number" if ok else
                               f"fps {v.get('capture_fps')}: no verbatim quote stating that number; dropped"))
        if not ok:
            v["capture_fps"] = None

    et = plan.get("event_table")
    if et:
        tab = next((t for t in tables if t.file == Path(et["file"]).name and t.sheet == et["sheet"]), None)
        if tab is None:
            cp.checks.append(Check("event_table", False, f"no table {et['file']}/{et['sheet']}"))
            plan["event_table"] = None
        else:
            for c in et["columns"]:
                if c["name"] not in tab.header:
                    cp.checks.append(Check(f"column {c['name']}", False, "not a header of the table"))
                    continue
                j = tab.header.index(c["name"])
                vals = [r[j] for r in tab.rows if isinstance(r[j], (int, float)) and not isinstance(r[j], bool)]
                c = dict(c)
                c["index"] = j
                c["si_factor"] = unit_factor(c["unit"])
                if c["quantity"] == "speed_uncertainty":
                    ev = c["evidence"].lower()
                    words = (c["name"].lower(), "relativ", "ratio", "fraction", "percent", "%", "absolute", "m/s", "m s")
                    if c["uncertainty_kind"] in ("absolute", "relative") and not (quoted(c["evidence"]) and
                                                                               any(w in ev for w in words)):
                        cp.checks.append(Check(f"column {c['name']} kind", False,
                                               f"'{c['uncertainty_kind']}' not supported by a verbatim quote about it; "
                                               "set to unknown"))
                        c["uncertainty_kind"] = "unknown"
                    elif c["uncertainty_kind"] == "relative" and vals and max(vals) >= 1:
                        cp.checks.append(Check(f"column {c['name']} kind", False,
                                               f"'relative' but values reach {max(vals):g} (a percentage?); set to unknown"))
                        c["uncertainty_kind"] = "unknown"
                    else:
                        cp.checks.append(Check(f"column {c['name']} kind", True,
                                               f"{c['uncertainty_kind']} ({'quote found' if c['evidence'] else 'no claim made'})"))
                if c["quantity"] in {"takeoff_speed"} | PAIRING and vals:
                    f = unit_factor(c["unit"])
                    if f is None:
                        cp.checks.append(Check(f"column {c['name']} unit", True,
                                               f"unit '{c['unit']}' is not absolute: kept for table checks, not used for pairing"))
                        c["si_factor"] = None
                        cp.columns[c["name"]] = c
                        continue
                    si = [x * f for x in vals]
                    lo, hi = {"takeoff_speed": (1e-2, 30), "takeoff_angle": (-90, 180), "jump_distance": (1e-5, 10),
                              "jump_height": (-10, 10), "airborne_time": (1e-4, 10)}[c["quantity"]]
                    plausible = lo <= min(si) and max(si) <= hi
                    cp.checks.append(Check(f"column {c['name']} range", plausible,
                                           f"{min(si):.4g}..{max(si):.4g} in SI" + ("" if plausible else " outside plausible range; dropped")))
                    if not plausible:
                        continue
                    c["si_factor"] = f
                cp.columns[c["name"]] = c

    seen = set()
    for cl in plan.get("claims", []):
        _apply_exponent(cl)
        key = (cl["quantity"], round(cl["value"], 12), cl["plus_minus"], cl["statistic"])
        if key in seen:                     # the same number stated twice (abstract and results)
            continue
        seen.add(key)
        ok_quote = quoted(cl["quote"]) and _number_in(cl["value"], cl["quote"])
        f = unit_factor(cl["unit"])
        cp.checks.append(Check(f"claim '{cl['quote'][:50]}'", ok_quote,
                               "quote and value found in the PDF" if ok_quote else "quote not found verbatim or value not in quote; dropped"))
        if ok_quote:
            cp.claims.append(dict(cl, si_factor=f))

    sr = plan.get("scale_reference", {})
    size_ok = sr.get("size_mm") is not None and quoted(sr.get("evidence", "")) and any(
        _number_in(sr["size_mm"] * f, sr["evidence"]) for f in (1, 0.1, 0.001))     # stated in mm, cm or m
    if sr.get("size_mm") is not None and not size_ok:
        cp.checks.append(Check("scale size", False, f"{sr['size_mm']} mm: no verbatim quote stating that size; dropped"))
        sr["size_mm"] = None
    am = plan.get("authors_speed_method", {})
    if am.get("family") not in ("unknown",) and not quoted(am.get("evidence", "")):
        cp.checks.append(Check("authors' method", False, "no verbatim quote; set to unknown"))
        am["family"] = "unknown"
    return cp


def _number_in(value: float, quote: str) -> bool:
    """The claimed value must appear in its own quote (as printed, allowing a leading zero to be dropped)."""
    q = quote.replace(",", "")
    nums = [float(x) for x in re.findall(r"(?<![\d.])\d*\.?\d+(?:[eE][-+]?\d+)?", q)]
    m = re.search(r"[x×]\s*10\s*[-−–]\s*(\d+)", q)            # '5.5 ± 14.4 x 10-3 s'
    if m:
        nums += [n * 10 ** -int(m.group(1)) for n in nums]
    return any(abs(n - value) <= 1e-9 + 1e-6 * abs(value) for n in nums)


def _apply_exponent(cl: dict) -> None:
    """'1.3 ± 0.7 x 10-3 s': a printed power of ten applies to the value and to its ±. Spark sometimes scales only the
    value; make the ± consistent when the quote shows both numbers unscaled."""
    m = re.search(r"[x×]\s*10\s*[-−–]\s*(\d+)", cl["quote"])
    if not m or cl.get("plus_minus") is None:
        return
    k = 10 ** -int(m.group(1))
    nums = [float(x) for x in re.findall(r"(?<![\d.])\d*\.?\d+", cl["quote"].replace(",", ""))]
    scaled_value = any(abs(n * k - cl["value"]) < 1e-12 + 1e-6 * abs(cl["value"]) for n in nums)
    raw_pm = any(abs(n - cl["plus_minus"]) < 1e-9 for n in nums)
    if scaled_value and raw_pm:
        cl["plus_minus"] = cl["plus_minus"] * k


def needs(claim: dict) -> str:
    """Route by what a claim is (code, not the model): aggregates are checked against the event table; single events
    go to the video via pairing; everything else is refused with a reason."""
    if claim.get("si_factor") is None and not claim.get("table_column"):
        return f"refuse: unit '{claim['unit']}' is not one the agent can measure or convert"
    if claim["statistic"] in ("mean", "median", "max", "min") and claim.get("table_column"):
        return "table_check"
    if claim["statistic"] in ("mean", "median", "max", "min"):
        return "refuse: statistic over several events and no event-table column to recompute it"
    if claim["statistic"] == "single_event" and claim["quantity"] in SI and claim.get("si_factor") is None:
        return f"refuse: unit '{claim['unit']}' is not one the agent can measure or convert"
    if claim["statistic"] == "single_event":
        return "video" if claim["quantity"] in {"takeoff_speed"} | PAIRING else \
            f"refuse: {claim['quantity']} is not measurable from a centroid track"
    return "refuse: not a single event or a recognised statistic"


def save(cp: CheckedPlan, path: Path) -> None:
    path.write_text(json.dumps({"plan": cp.plan, "checks": [c.__dict__ for c in cp.checks],
                                "columns": cp.columns, "claims": cp.claims}, indent=2, ensure_ascii=False))
