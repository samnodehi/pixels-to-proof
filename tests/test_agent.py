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


def test_frame_step_from_overlay():
    from pixels_to_proof.agent import _frame_step
    assert _frame_step({"overlay_text": "Filmed at 5000 fps\nPlayback 4x faster"})[0] == 4
    assert _frame_step({"overlay_text": "captured - 3,200 frames/second\nplayback - 30 frames/second"})[0] == 1
    assert _frame_step({"overlay_text": "Filmed & Playback at 5000 fps"})[0] == 1
    assert _frame_step({"overlay_text": "Playback 2x slower"})[0] is None
    assert _frame_step({"overlay_text": "playback 2.5x faster"})[0] is None
    assert _frame_step({"overlay_text": "playback 2x faster\nplayback 4x faster"})[0] is None


def test_split_proposal_gate():
    from pixels_to_proof.agent import check_split
    sampled = list(range(173, 572, 8))
    recs, _ = check_split([{"first_frame": 181, "last_frame": 365}, {"first_frame": 405, "last_frame": 563}],
                          173, 571, sampled, 30)
    assert recs == [(173, 384), (405, 571)]          # ends mid-transition, the next starts where Spark says
    assert check_split([{"first_frame": 173, "last_frame": 571}], 173, 571, sampled, 30)[0] == [(173, 571)]
    assert check_split([{"first_frame": 173, "last_frame": 400}, {"first_frame": 390, "last_frame": 571}],
                       173, 571, sampled, 30)[0] == []                       # overlap
    assert check_split([{"first_frame": 173, "last_frame": 190}, {"first_frame": 200, "last_frame": 571}],
                       173, 571, sampled, 30)[0] == []                       # too short
    assert check_split([{"first_frame": 100, "last_frame": 300}, {"first_frame": 320, "last_frame": 571}],
                       173, 571, sampled, 30)[0] == []                       # outside the shot


def test_wall_target_scale():
    from pixels_to_proof import scale
    img = np.full((400, 600), 180, np.uint8)
    img[300:320, :100] = 40                     # take-off platform from the left border, tip at x=99
    img[:, 560:] = 50                           # vertical landing target, face at x=560
    g = scale.platform_gap(img)
    assert g.right_kind == "wall" and abs(g.right_tip_px - 559.5) < 1.5 and abs(g.left_tip_px - 100) <= 3
    img2 = np.full((400, 600), 180, np.uint8)
    img2[300:320, :100] = 40
    img2[310:330, 480:] = 40                    # a second platform, no wall
    assert scale.platform_gap(img2).right_kind == "rod"


def test_flight_ends_at_a_wall_and_drag_is_named():
    from pixels_to_proof import measure
    fps, g, n = 1250.0, 9.80665, 160
    t = np.arange(n) / fps
    t_off, t_hit = 0.02, 0.09
    x = np.where(t < t_off, 0.0, np.minimum(0.6 * (t - t_off), 0.6 * (t_hit - t_off)))
    tf = np.clip(t - t_off, 0, t_hit - t_off)
    y = np.where(t < t_off, 0.0, 0.7 * tf - 0.5 * g * tf ** 2)
    mm = 0.025
    cx, cy = x * 1000 / mm + 100, 900 - y * 1000 / mm
    k = measure.kinematics(np.arange(n), cx, cy, fps, mm)
    assert abs(k.landing_frame - round(t_hit * fps)) <= 3              # stopped at the wall, not at the clip end
    assert abs(k.g_fit_rel_err) < 0.02 and k.drag_like == ""
    assert abs(k.end_height_mm - (0.7 * 0.07 - 0.5 * g * 0.07 ** 2) * 1000) < 0.3


def test_near_vertical_flight_is_not_cut_by_jitter():
    from pixels_to_proof import measure
    rng = np.random.default_rng(3)
    fps, n, mm = 500.0, 200, 0.03
    t = np.arange(n) / fps
    tf = np.clip(t - 0.04, 0, None)
    y = np.where(t < 0.04, 0, 1.2 * tf - 0.5 * 9.81 * tf ** 2)
    x = np.where(t < 0.04, 0, 0.02 * tf)
    for _ in range(50):
        cx = x * 1000 / mm + rng.normal(0, 2, n)
        cy = 500 - y * 1000 / mm + rng.normal(0, 2, n)
        _, X, Y = measure.to_metres(np.arange(n), cx, cy, mm)
        assert measure.flight_window(Y, 0.0005, X) == measure.flight_window(Y, 0.0005)


def test_black_pillarbox_is_not_a_wall():
    from pixels_to_proof import scale
    img = np.full((720, 1280), 170, np.uint8)
    img[500:520, :200] = 40
    img[:, 1120:] = 0
    assert scale._wall_face(img.astype(np.float32)) is None


def test_table_check_subset_and_circular_mean():
    rows = [["male", a] for a in (10.0, 20.0, 50.0)] + [["female", a] for a in (5.0, 6.0, 7.0)]
    t = ingest.Table(file="t.csv", sheet="t", header=["sex", "angle"], rows=rows, header_row=0)
    cols = {"angle": {"name": "angle", "quantity": "takeoff_angle", "unit": "deg", "index": 1, "si_factor": 1.0}}
    import math
    a = [math.radians(v) for v in (10.0, 20.0, 50.0)]
    cm = math.degrees(math.atan2(sum(map(math.sin, a)) / 3, sum(map(math.cos, a)) / 3))
    claim = {"quantity": "takeoff_angle", "value": round(cm, 2), "plus_minus": None, "unit": "deg",
             "quote": f"males {round(cm, 2):.2f} deg", "statistic": "mean", "spread": "none", "table_column": "angle",
             "si_factor": 1.0, "row_filter": {"column": "sex", "value": "male"}}
    assert tablecheck.check(claim, t, cols)["outcome"] == tablecheck.NOT_CHECKED          # arithmetic 26.67
    r = tablecheck.check(claim, t, cols, circular=True)
    assert r["outcome"] == tablecheck.MATCHES and r["stats"] == "circular" and r["n_rows"] == 3
    fem = dict(claim, value=6.0, quote="females 6.0 deg", row_filter={"column": "sex", "value": "female"})
    assert tablecheck.check(fem, t, cols)["outcome"] == tablecheck.MATCHES


def test_flight_cut_by_the_shot_end_is_flagged():
    from pixels_to_proof import measure
    fps, n, mm = 1250.0, 90, 0.025
    t = np.arange(n) / fps
    tf = np.clip(t - 0.02, 0, None)
    x, y = 0.6 * tf, 0.7 * tf - 0.5 * 9.80665 * tf ** 2          # still rising when the clip ends
    k = measure.kinematics(np.arange(n), x * 1000 / mm + 100, 900 - y * 1000 / mm, fps, mm)
    assert k.truncated


def test_table_check_per_animal_and_truncation():
    rows = [["a", "full", 4.0, 90.069], ["a", "full", 4.0, 120.0], ["b", "full", 6.0, 130.0],
            ["a", "takeoff", 9.0, 140.0], ["c", "takeoff", 3.0, 125.0]]
    t = ingest.Table(file="t.csv", sheet="t", header=["id", "cond", "mass", "acc"], rows=rows, header_row=0)
    cols = {"id": {"name": "id", "quantity": "animal_id", "unit": "", "index": 0, "si_factor": None},
            "mass": {"name": "mass", "quantity": "mass", "unit": "mg", "index": 2, "si_factor": None},
            "acc": {"name": "acc", "quantity": "acceleration", "unit": "m/s2", "index": 3, "si_factor": 1.0}}
    claim = {"quantity": "mass", "value": 5.5, "plus_minus": None, "unit": "mg", "quote": "mass 5.5 mg, n=4",
             "statistic": "mean", "spread": "none", "table_column": "mass", "si_factor": None, "n_events": 4,
             "row_filter": {"column": None, "value": None}}
    r = tablecheck.check(claim, t, cols)       # rows: 5.2; per (id, cond): (4 + 6 + 9 + 3) / 4 = 5.5
    assert r["outcome"] == tablecheck.MATCHES and r["stats"] == "per_animal"
    low = {"quantity": "acceleration", "value": 90.06, "plus_minus": None, "unit": "m/s2", "quote": "lowest 90.06 m s-2",
           "statistic": "min", "spread": "none", "table_column": "acc", "si_factor": 1.0, "n_events": None,
           "row_filter": {"column": None, "value": None}}
    r = tablecheck.check(low, t, cols)
    assert r["outcome"] == tablecheck.NOT_CHECKED and "truncated" in r["reason"]


def test_population_sd_is_named():
    rows = [[v] for v in (70.0, 72.0, 80.0, 71.0)]
    t = ingest.Table(file="t.csv", sheet="t", header=["w"], rows=rows, header_row=0)
    cols = {"w": {"name": "w", "quantity": "mass", "unit": "kg", "index": 0, "si_factor": None}}
    import statistics
    psd = round(statistics.pstdev([70, 72, 80, 71]), 2)
    claim = {"quantity": "mass", "value": 73.25, "plus_minus": psd, "unit": "kg", "quote": f"weight 73.25 ± {psd} kg",
             "statistic": "mean", "spread": "sd", "table_column": "w", "si_factor": None, "n_events": None,
             "row_filter": {"column": None, "value": None}}
    r = tablecheck.check(claim, t, cols)
    assert r["outcome"] == tablecheck.MATCHES and r["stats"] == "population_sd"
