"""Unit tests for the audit agent's code-side checks (no model calls)."""
import numpy as np

from pixels_to_proof import ingest, pairing, plan, tablecheck
from pixels_to_proof.agent import _overlay_fps, _spar
from pixels_to_proof.measure import Kinematics


def test_licence_gate():
    assert ingest.licence("distributed under the terms of the Creative Commons Attribution License, which")[0] == "CC BY"
    assert ingest.licence("licensed under CC BY-NC 4.0 (Creative Commons licence)")[0] is None
    assert ingest.licence("Copyright 2020 Elsevier. All rights reserved.")[0] is None
    assert ingest.licence("This work is in the public domain in the USA.")[0] == "public domain"


def test_quote_check_ignores_pdf_spacing():
    text = ingest.normalise("larvae achieved a takeoff velocity of\n   0.47 ± 0.15 m s −1 with the fastest")
    assert ingest.quote_in_text("a takeoff velocity of 0.47 ± 0.15 m s-1", text)
    assert not ingest.quote_in_text("a takeoff velocity of 0.57 ± 0.15 m s-1", text)


def test_exponent_applies_to_value_and_pm():
    c = {"quote": "airborne for 1.3 ± 0.7 x 10-3 s", "value": 0.0013, "plus_minus": 0.7}
    plan._apply_exponent(c)
    assert abs(c["plus_minus"] - 0.0007) < 1e-12
    assert plan._number_in(0.0013, c["quote"])


def _table():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(20):
        ang, dist, h, t, v = 30 + 2 * i, 0.01 + 0.0005 * i, 0.004 + 0.0002 * i, 0.05 + 0.002 * i, 0.4 + 0.01 * i
        rows.append([f"jump{i}", ang, dist, h, t, v, 0.05, ang + rng.normal(0, 20)])
    header = ["id", "angle", "dist", "height", "airtime", "speed", "err", "bodyangle"]
    t = ingest.Table(file="t.csv", sheet="t", header=header, rows=rows, header_row=0)
    cols = {}
    for j, (name, q, u) in enumerate([("id", "event_id", ""), ("angle", "takeoff_angle", "deg"),
                                      ("dist", "jump_distance", "m"), ("height", "jump_height", "m"),
                                      ("airtime", "airborne_time", "s"), ("speed", "takeoff_speed", "m/s"),
                                      ("err", "speed_uncertainty", "ratio"), ("bodyangle", "body_angle", "deg")]):
        cols[name] = {"name": name, "quantity": q, "unit": u, "index": j, "si_factor": plan.unit_factor(u)}
    return t, cols


def _k(ang, dist, h, t):
    return Kinematics(0, 0, t, 9.81, 0.0, 0.0, 0.5, (0.49, 0.51), ang, h * 1000, dist * 1000, 0.5, (0.5, 0.5))


def test_pairing_picks_the_matching_row_without_the_speed():
    t, cols = _table()
    r = pairing.pair(_k(30 + 2 * 7, 0.01 + 0.0005 * 7, 0.004 + 0.0002 * 7, 0.05 + 0.002 * 7), t, cols, "id", 2.0)
    assert r["ok"] and r["row_id"] == "jump7"
    # halfway between two rows: refused as ambiguous
    r = pairing.pair(_k(30 + 2 * 7.5, 0.01 + 0.0005 * 7.5, 0.004 + 0.0002 * 7.5, 0.05 + 0.002 * 7.5), t, cols, "id", 2.0)
    assert not r["ok"]


def test_pairing_ignores_body_angles():
    t, cols = _table()
    feats = pairing.pair(_k(44, 0.0135, 0.0054, 0.064), t, cols, "id", 2.0)["features"]
    assert "body_angle" not in feats and "takeoff_angle" in feats


def test_table_check_matches_printed_digits_and_other_columns():
    t, cols = _table()
    speeds = [r[5] for r in t.rows]
    m, sd = float(np.mean(speeds)), float(np.std(speeds, ddof=1))
    claim = {"quote": f"speed {m:.2f} ± {sd:.2f} m/s", "value": round(m, 2), "plus_minus": round(sd, 2),
             "unit": "m/s", "statistic": "mean", "spread": "sd", "table_column": "speed", "si_factor": 1.0,
             "quantity": "takeoff_speed"}
    assert tablecheck.check(claim, t, cols)["outcome"] == tablecheck.MATCHES
    claim_wrong_col = dict(claim, table_column="angle")      # dimension differs: not even tried
    assert tablecheck.check(claim_wrong_col, t, cols)["outcome"] == tablecheck.OTHER_COLUMN  # found on speed
    bad = dict(claim, value=round(m + 0.05, 2), quote=f"speed {m + 0.05:.2f} ± {sd:.2f} m/s")
    assert tablecheck.check(bad, t, cols)["outcome"] == tablecheck.NOT_CHECKED


def test_needs_routes_by_statistic():
    assert plan.needs({"statistic": "mean", "table_column": "x", "unit": "m/s", "si_factor": 1.0,
                       "quantity": "takeoff_speed"}) == "table_check"
    assert plan.needs({"statistic": "single_event", "unit": "m/s", "si_factor": 1.0,
                       "quantity": "takeoff_speed"}) == "video"
    assert plan.needs({"statistic": "single_event", "unit": "ms", "si_factor": 1e-3,
                       "quantity": "other_duration"}).startswith("refuse")


def test_overlay_fps_requires_the_number_to_be_printed():
    text = "Laemophloeus\ncaptured - 3,200 frames/second\nplayback - 30 frames/second"
    assert _overlay_fps({"capture_fps": 3200, "overlay_text": text})[0] == 3200
    assert _overlay_fps({"capture_fps": 1000, "overlay_text": text})[0] == 3200      # code parses the text instead
    assert _overlay_fps({"capture_fps": 1000, "overlay_text": "no rate here"})[0] is None


def test_spar_parsing():
    assert _spar({"parameters": "smooth.Pspline spar=0.00000001 method=1", "evidence": ""}) == 1e-8
    assert _spar({"parameters": "", "evidence": "with a smoothing spar value of 10-8 [59]"}) == 1e-8


def test_unit_with_printed_power_of_ten():
    assert abs(plan.unit_factor("x 10-3 s") - 1e-3) < 1e-15
    assert plan.unit_dim("x 10-3 s") == "time"
    assert plan.unit_factor("m s-1") == 1.0 and plan.unit_factor("bananas") is None


def test_quote_with_joined_passages():
    text = ingest.normalise("A spline was fitted with spar 10-8. This value was chosen by eye. Speeds were maxima.")
    assert ingest.quote_in_text("A spline was fitted with spar 10-8 ... Speeds were maxima.", text)
    assert not ingest.quote_in_text("A spline was fitted with spar 10-8. Speeds were maxima.", text)


def test_merge_takes_only_rejected_fields():
    old = {"authors_speed_method": {"family": "unknown", "parameters": "", "evidence": "x"},
           "scale_reference": {"kind": "grid", "size_mm": 5.0, "evidence": "q"}, "videos": [], "event_table": None,
           "claims": [{"quote": "speed was 0.5 m/s in one", "quantity": "takeoff_speed", "value": 0.5},
                      {"quote": "angle was 40 degrees overall", "quantity": "takeoff_angle", "value": 40.0}]}
    new = {"authors_speed_method": {"family": "linear_fit", "parameters": "p", "evidence": "e"},
           "scale_reference": {"kind": "ruler", "size_mm": 1.0, "evidence": "r"}, "videos": [], "event_table": None,
           "claims": [{"quote": "speed of 0.5 m/s", "quantity": "takeoff_speed", "value": 0.5},
                      {"quote": "angle 41 degrees", "quantity": "takeoff_angle", "value": 41.0}]}
    rejected = [plan.Check("authors' method", False, ""), plan.Check("claim 'speed was 0.5 m/s in one'", False, "")]
    m = plan.merge(old, new, rejected)
    assert m["authors_speed_method"]["family"] == "linear_fit"
    assert m["scale_reference"]["size_mm"] == 5.0                    # accepted field untouched
    assert {c["quote"] for c in m["claims"]} == {"angle was 40 degrees overall", "speed of 0.5 m/s"}


def test_licence_gate_normalises_dashes():
    assert ingest.licence("published under a CC BY–NC 4.0 licence")[0] is None
    assert ingest.licence("CC BY‑NC‑ND licence")[0] is None


def test_table_check_fails_closed_on_unprinted_value():
    t, cols = _table()
    claim = {"quote": "mean airborne time was short", "value": 0.0012, "plus_minus": None, "unit": "s",
             "statistic": "mean", "spread": "none", "table_column": "airtime", "si_factor": 1.0,
             "quantity": "airborne_time"}
    assert tablecheck.check(claim, t, cols)["outcome"] == tablecheck.NOT_CHECKED


def test_pairing_tolerates_blank_cells():
    t, cols = _table()
    t.rows[7][3] = None
    r = pairing.pair(_k(30 + 2 * 7, 0.01 + 0.0005 * 7, 0.004 + 0.0002 * 7, 0.05 + 0.002 * 7), t, cols, "id", 2.0)
    assert r["row_id"] == "jump7" and r["detail"]["jump_height"]["row"]["height"] is None


def test_pairing_mirrors_right_to_left_jumps():
    t, cols = _table()
    k = _k(180 - (30 + 2 * 7), -(0.01 + 0.0005 * 7), 0.004 + 0.0002 * 7, 0.05 + 0.002 * 7)
    assert pairing.pair(k, t, cols, "id", 2.0)["row_id"] == "jump7"


def test_speed_column_in_wrong_unit_is_rejected():
    t, _ = _table()
    raw = {"videos": [], "event_table": {"file": "t.csv", "sheet": "t", "rows_are": "jumps", "columns": [
        {"name": "speed", "quantity": "takeoff_speed", "unit": "cm/s", "uncertainty_of": None,
         "uncertainty_kind": "not_an_uncertainty", "evidence": ""}]},
        "scale_reference": {"kind": "none", "size_mm": None, "evidence": ""}, "object_phrase": "x",
        "authors_speed_method": {"family": "unknown", "parameters": "", "evidence": ""}, "claims": []}
    cp = plan.check(raw, "text", "", [t], "")
    assert "speed" not in cp.columns


def test_track_start_gate_keeps_a_short_flight_in_a_long_track():
    from pixels_to_proof.track import Point, quality
    rng = np.random.default_rng(1)
    pts, x, y = [], 300.0, 300.0
    for i in range(520):
        if 100 <= i < 115:              # 15-frame flight in a 520-frame clip
            x += 6.0
            y -= 3.0 - 0.4 * (i - 100)
        pts.append(Point(i, x + rng.normal(0, 0.3), y + rng.normal(0, 0.3), 900, 0, 0, 1, 1))
    assert quality(pts)["ok"]


def test_merge_takes_a_corrected_value_from_the_same_sentence():
    base = {"authors_speed_method": {}, "scale_reference": {}, "videos": [], "event_table": None,
            "claims": [{"quote": "Larvae reached takeoff velocities of 0.57", "quantity": "takeoff_speed", "value": 0.57}]}
    new = dict(base, claims=[{"quote": "Larvae reached takeoff velocities of 0.47", "quantity": "takeoff_speed",
                              "value": 0.47}])
    m = plan.merge(base, new, [plan.Check("claim 'Larvae reached takeoff velocities of 0.57'", False, "")])
    assert [c["value"] for c in m["claims"]] == [0.47]
