"""Fault injection for the audit agent: corrupt one model proposal at a time (as a wrong model answer would) and
check what the agent does with it. Each mutation starts from the cached unmutated run, so only the affected stages
are recomputed (tracking is re-run only when the box changes).

Outcomes per mutation, compared with the unmutated run:
  caught     a gate rejected the corrupted field (or the affected verdict became CANNOT MEASURE / a refusal)
  recovered  the agent still produced the unmutated verdict (after a fallback or re-proposal)
  WRONG      a different verdict than the unmutated one that is not a refusal  -> must never happen

Usage: python -m bench.faults BUNDLE BASE_RUN_DIR --out DIR
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from pixels_to_proof import agent, plan


def _load(p: Path):
    return json.loads(p.read_text())


def mutations(base: Path) -> list[tuple[str, str, callable]]:
    """(name, family, function(run_dir)) — each edits cached model outputs in a copy of the base run."""
    def plan_edit(fn):
        def apply(run: Path):
            raw, usage = _load(run / "plan_raw.json")
            fn(raw)
            (run / "plan_raw.json").write_text(json.dumps([raw, usage]))
        return apply

    def col(raw, name):
        return next(c for c in raw["event_table"]["columns"] if c["name"] == name)

    hero = next(v["unit"] for v in _load(base / "report.json")["videos"]
                if v["verdict"] in ("REPRODUCED", "NOT REPRODUCED"))

    def frame_edit(fn, unit=hero):
        def apply(run: Path):
            f = run / "units" / unit / "frame_reading.json"
            fr, usage = _load(f)
            fn(fr)
            f.write_text(json.dumps([fr, usage]))
            for t in (run / "units" / unit).glob("track_*.json"):
                t.unlink()                      # the track depends on the box: recompute
            for t in (run / "units" / unit).glob("rebox_*.json"):
                t.unlink()
        return apply

    def swap_angle(raw):
        col(raw, "TakeoffAngleDeg")["quantity"] = "body_angle"
        col(raw, "TakeoffBAngle")["quantity"] = "takeoff_angle"

    def dist_unit(raw):
        col(raw, "DistanceRawm")["unit"] = "mm"
        col(raw, "DistanceTrajm")["unit"] = "mm"

    def speed_unit(raw):
        col(raw, "velocity.max")["unit"] = "mm/s"

    def err_absolute(raw):
        c = col(raw, "VelError")
        c["uncertainty_kind"], c["evidence"] = "absolute", "the error is given in m/s"

    def grid_size(raw):
        raw["scale_reference"]["size_mm"] = 10.0

    def video_fps(raw):
        for v in raw["videos"]:
            if v["capture_fps"] == 3200:
                v["capture_fps"] = 1000

    def wrong_quote(raw):
        for c in raw["claims"]:
            if c["quantity"] == "takeoff_speed" and c["statistic"] == "mean":
                c["value"] = 0.57          # a misread number

    def stat_single(raw):
        for c in raw["claims"]:
            if c["quantity"] == "takeoff_speed" and c["statistic"] == "mean":
                c["statistic"] = "single_event"

    def overlay_fps(fr):
        fr["capture_fps"] = 1000           # Spark misreads the printed rate

    def overlay_fps_text(fr):
        fr["capture_fps"] = 1000
        fr["overlay_text"] = fr["overlay_text"].replace("3,200", "1,000")   # misread consistently

    def bad_box(fr):
        fr["object_box"] = [5, 5, 120, 90]  # top-left corner: background

    def no_grid(fr):
        fr["reference_kind"] = "none"

    return [
        ("column map: trajectory angle swapped with a body-posture angle", "plan", plan_edit(swap_angle)),
        ("column unit: distances in mm instead of m", "plan", plan_edit(dist_unit)),
        ("column unit: speed in mm/s instead of m/s", "plan", plan_edit(speed_unit)),
        ("uncertainty: relative error claimed absolute, unsupported quote", "plan", plan_edit(err_absolute)),
        ("scale: grid square 10 mm instead of 5 mm", "plan", plan_edit(grid_size)),
        ("frame rate: paper rate 1,000 fps instead of 3,200", "plan", plan_edit(video_fps)),
        ("claim: misread value 0.57 instead of 0.47", "plan", plan_edit(wrong_quote)),
        ("claim: mean labelled a single event", "plan", plan_edit(stat_single)),
        ("frame read: rate 1,000 fps (not printed)", "frame", frame_edit(overlay_fps)),
        ("frame read: rate 1,000 fps, overlay misread to match", "frame", frame_edit(overlay_fps_text)),
        ("frame read: object box on the background", "frame", frame_edit(bad_box)),
        ("frame read: grid not seen", "frame", frame_edit(no_grid)),
    ]


def classify(base_rep: dict, rep: dict, new_rejections: list[str], reproposals: int) -> tuple[str, str]:
    """WRONG: a verdict changed to a different non-refusal. caught: a check fired and the affected result became a
    refusal / not-checked. recovered: a check fired (or Spark re-proposed) and the final results equal the unmutated
    run. no effect: nothing fired and nothing changed (the corrupted field was overridden or not needed)."""
    bv, mv = base_rep["summary"]["videos"], rep.get("summary", {}).get("videos", {})
    # value in SI units, so a claim the re-proposal states in another unit (5.5 ms for 0.0055 s) is the same claim
    key = lambda c: (c["quantity"], c["statistic"], plan._claim_key(c)[1],
                     None if c.get("plus_minus") is None else
                     float(f"{float(c['plus_minus']) * (plan.unit_factor(c.get('unit', '')) or 1.0):.6g}"))
    bc = {key(c): c["outcome"] for c in base_rep["claims"]}
    mc = {key(c): c["outcome"] for c in rep.get("claims", [])}
    changed_v = {u: (bv[u], mv.get(u)) for u in bv if mv.get(u) != bv[u]}
    changed_c = {k: (bc[k], mc.get(k)) for k in bc if mc.get(k) != bc[k]}
    added_c = {k: (None, v) for k, v in mc.items() if k not in bc}
    wrong = [f"{u}: {a} -> {b}" for u, (a, b) in changed_v.items()
             if b not in (None, "CANNOT MEASURE") and a != b]
    wrong += [f"claim {k}: {a} -> {b}" for k, (a, b) in {**changed_c, **added_c}.items()
              if b in ("MATCHES TABLE", "MATCHES OTHER COLUMN") and a not in ("MATCHES TABLE", "MATCHES OTHER COLUMN")
              and not any(k[0] == kb[0] and k[2] == kb[2] for kb in bc)]      # a value the base run never matched
    if wrong:
        return "WRONG", "; ".join(wrong)
    fired = bool(new_rejections) or reproposals > 0
    if not changed_v and not changed_c and not added_c:
        return ("recovered", "a check fired and the final results equal the unmutated run") if fired else \
            ("no effect", "nothing fired and nothing changed")
    parts = [f"{u}: {a} -> {b}" for u, (a, b) in changed_v.items()] + \
            [f"claim {k}: {a} -> {b}" for k, (a, b) in {**changed_c, **added_c}.items()]
    return "caught", "; ".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", type=Path)
    ap.add_argument("base", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    base_rep = _load(a.base / "report.json")
    rows = []
    for i, (name, family, apply) in enumerate(mutations(a.base)):
        run = a.out / f"m{i:02d}"
        if run.exists():
            shutil.rmtree(run)
        shutil.copytree(a.base, run, ignore=shutil.ignore_patterns("ledger.json", "report.json", "receipt.mp4",
                                                                     "plan_checked.json", "plan_raw_v*.json"))
        # Mutate the plan the base run accepted (after any re-proposal and merge); re-proposals in the mutated run
        # are live model calls.
        accepted = _load(a.base / "plan_checked.json")["plan"]
        (run / "plan_raw.json").write_text(json.dumps([accepted, {}]))
        apply(run)
        rep, err = None, None
        try:
            rep = agent.run_audit(a.bundle, run, run_id=f"fault-{i:02d}")
        except Exception as exc:                     # a crash is a failure of the harness or the agent; report it
            err = f"{type(exc).__name__}: {exc}"
        led = _load(run / "ledger.json") if (run / "ledger.json").exists() else {"events": []}
        key = lambda e: f"{e['gate']} [{e.get('ref', '')[-12:]}]: {e['note'][:110]}"
        rejections = [key(e) for e in led["events"] if e["kind"] == "gate" and not e["ok"]]
        base_rej = {key(e) for e in _load(a.base / "ledger.json")["events"] if e["kind"] == "gate" and not e["ok"]}
        new_rej = [r for r in rejections if r not in base_rej]
        reprop = sum(1 for e in led["events"] if e["kind"] == "model" and e["role"] == "re-propose box")
        outcome, detail = ("ERROR", err) if err else classify(base_rep, rep, new_rej, reprop)
        rows.append({"mutation": name, "family": family, "outcome": outcome, "detail": detail,
                     "new_gate_rejections": new_rej, "spark_reproposals": reprop})
        print(f"[{outcome}] {name} | {detail[:150]} | new rejections: {len(new_rej)}", flush=True)
    (a.out / "faults.json").write_text(json.dumps(rows, indent=1))
    n = len(rows)
    md = ["# Fault injection", "",
          f"Each row corrupts one model proposal of a real audit ({a.bundle.name}, base run {base_rep['run_id']}) the way "
          "a wrong model answer would, then re-runs the agent. Re-proposals in these runs are live model calls, so a "
          "repeat run can differ.", "",
          "- **caught**: a check fired and the affected result became a refusal or NOT CHECKED",
          "- **recovered**: a check fired (or Muse Spark re-proposed) and the final results equal the uncorrupted run",
          "- **no effect**: nothing fired and nothing changed (code overrode the field, or it was not needed)",
          "- **WRONG**: a verdict changed to a different non-refusal — must not happen", "",
          "| mutation | outcome | what happened | gate rejections that fired |", "|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['mutation']} | {r['outcome']} | {r['detail'][:160]} | "
                  f"{'; '.join(r['new_gate_rejections'])[:200] or '—'} |")
    counts = {k: sum(r["outcome"] == k for r in rows) for k in ("caught", "recovered", "no effect", "WRONG", "ERROR")}
    md += ["", f"caught {counts['caught']}, recovered {counts['recovered']}, no effect {counts['no effect']}, "
               f"wrong verdicts {counts['WRONG']}, errors {counts['ERROR']} (of {n})"]
    (a.out / "FAULTS.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[-1:]))


if __name__ == "__main__":
    main()
