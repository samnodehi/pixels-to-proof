"""Run the full pipeline on every synthetic case and score it against the planted truth.

Usage: python -m bench.run CASES_DIR --out RUNS_DIR --workers 4
Writes RUNS_DIR/results.json and RUNS_DIR/summary.md.
"""
from __future__ import annotations

import argparse
import json
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from pixels_to_proof.pipeline import run


def one(case_file: Path, runs: Path) -> dict:
    case = json.loads(case_file.read_text())
    out = runs / case["id"]
    row = {"id": case["id"], "truth": case["truth"], "claim": case["claim"]["value"]}
    try:
        log = run(case_file, out)
        v = log["verdict"]
        row.update(verdict=v["label"], spark_fps_ok=log["stages"]["time"]["agree"],
                   spark_scale_diff=log["stages"]["scale"]["spark_rel_diff"],
                   prompt=next((a["prompt"] for a in log["stages"]["track"]["attempts"] if a["accepted"]), None),
                   rejected_tracks=sum(not a["accepted"] for a in log["stages"]["track"]["attempts"]))
        if "kinematics" in log:
            k = log["kinematics"]
            row.update(v_est=k["v0_ballistic"], lo=v["measured_lo"], hi=v["measured_hi"], g_fit=k["g_fit"],
                       frames=log["stages"]["track"]["frames_tracked"])
    except Exception as exc:
        row.update(verdict="ERROR", error=f"{type(exc).__name__}: {exc}")
        (out / "error.txt").parent.mkdir(parents=True, exist_ok=True)
        (out / "error.txt").write_text(traceback.format_exc())
    return row


def summarise(rows: list[dict]) -> str:
    ok = [r for r in rows if "v_est" in r and not r["truth"]["wrong_fps_in_case"]]
    errs = [abs(r["v_est"] - r["truth"]["v0"]) / r["truth"]["v0"] for r in ok]
    lines = ["# Synthetic calibration results", "",
             f"Cases: {len(rows)}; pipeline errors: {sum(r['verdict'] == 'ERROR' for r in rows)}", ""]
    if errs:
        lines += ["## Measurement accuracy (cases with the correct frame rate)",
                  f"- |measured - true| / true: median {np.median(errs):.2%}, 90th percentile {np.percentile(errs, 90):.2%}, max {max(errs):.2%}",
                  f"- true value inside the reported interval: {sum(r['lo'] <= r['truth']['v0'] <= r['hi'] for r in ok)}/{len(ok)}",
                  f"- Muse Spark read the frame rate from the overlay correctly: {sum(bool(r['spark_fps_ok']) for r in ok)}/{len(ok)}",
                  f"- object followed via Muse Spark's box: {sum(r.get('prompt') == 'box from Muse Spark' for r in ok)}/{len(ok)}; "
                  f"cases where a track was rejected by the quality check and another prompt used: {sum(r.get('rejected_tracks', 0) > 0 for r in ok)}",
                  ""]
    by = defaultdict(list)
    for r in rows:
        if r["truth"]["wrong_fps_in_case"]:
            by["wrong frame rate in case"].append(r)
        else:
            by[f"planted error {abs(r['truth']['planted_error']):.0%}"].append(r)
    lines += ["## Verdicts", "", "| group | n | expected | REPRODUCED | NOT REPRODUCED | CANNOT MEASURE | ERROR |",
              "|---|---|---|---|---|---|---|"]
    for g in sorted(by):
        rs = by[g]
        exp = rs[0]["truth"]["expected"]
        c = lambda lab: sum(r["verdict"] == lab for r in rs)
        lines.append(f"| {g} | {len(rs)} | {exp} | {c('REPRODUCED')} | {c('NOT REPRODUCED')} | {c('CANNOT MEASURE')} | {c('ERROR')} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    files = sorted(a.cases.glob("case_*/case.json"))
    with ThreadPoolExecutor(a.workers) as ex:
        rows = list(ex.map(lambda f: one(f, a.out), files))
    (a.out / "results.json").write_text(json.dumps(rows, indent=2))
    md = summarise(rows)
    (a.out / "summary.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
