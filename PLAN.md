# Pixels to Proof - project plan

Meta Global AI Developer Hackathon, Indie track (solo). Build window Oct 27 – Nov 4, 2026, submission due
Wed Nov 4, 9:00 PM ET. All work in this repository was written during the hackathon.

## Objective
Given what a journal published with a paper (PDF, supplementary videos, data tables, scripts), audit its kinematic
claims: recompute statistics from the paper's own tables, re-measure single jumps from its videos, and return per claim
and per shot an outcome with evidence or a refusal naming the failing check. The model proposes; code checks and
measures. Judging criteria (equal weight): impact, use of Meta AI tooling beyond basic integration, technical depth and
execution, demo; target also the Best Agentic Use-Case bonus.

## Architecture
See `DESIGN.md` (as built) and `DECISIONS.md` (choices and their history). Core: `pixels_to_proof/agent.py`
(G0 licence → shots + frame reads → plan with G1 and re-proposal → routing → table check → G4 inputs → SAM track with
G5 and box re-proposal → self-checks → G3 blind pairing → G6 verdict → ledger and receipt). The older case-file
pipeline (`pipeline.py`, `cases/`) remains for the synthetic benchmark and the hand-prepared spider montage case.

## Stages
- S0 Day-1 spike: DONE 2026-10-27 (beetle jump re-measured from a hand-prepared case).
- S1 Measuring core + CLI + tests: DONE 2026-10-27.
- S2 Synthetic calibration: DONE 2026-10-27 (`bench/RESULTS_seed2026.md`); re-run identical on 2026-10-28 after the
  agent changes.
- S3 Spider montage (hand-prepared cases): DONE 2026-10-27, all CANNOT MEASURE with reasons.
- S4 Web app + Space: DONE 2026-10-27; replaced 2026-10-28 by the ledger-driven Audit view (recorded runs, labelled
  live re-run of bundled papers, rate limited; no uploads).
- S5 Audit agent, hands-off on the beetle bundle: DONE 2026-10-28 (council → reviews → build → impact/doc review →
  hardening). Clean-commit recorded run `beetle-20261028-7a8c0e6`.
- S6 Fault injection: harness done; final run on the clean base in progress (results to `showcase/faults.md`).
- S7 Second hands-off paper: NEXT. Spider (needs the main-paper PDF and montage splitting in the agent) and/or the
  peacock spider candidate (J Exp Biol 2025, CC BY; video on Zenodo, table on Dryad); downloads need Sam (the
  container's proxy blocks those hosts).
- S8 Demo video (3 min, English AI voice "daniel", captions), README, submission: Nov 1–3; public repo and Space only
  with Sam's OK.

## Findings so far
- Beetle (agent, hands-off): 18 claims — 11 reproduced from the table, 2 by another column, 3 by no column, 2 refused;
  12 shots — 11 refused before tracking with reasons, 1 measured; blind pairing row 488 (4.7×); REPRODUCED
  0.405 ± 0.024 vs 0.436 [0.425–0.447]; authors' method replica 0.398 (second reading). Scale: our grid 5.0 mm vs the
  authors' implied 4.85 mm (3 %).
- Beetle text vs table (not findings about the authors; aggregation is not always stated): "leaving the ground at an
  angle of 79.6 ± 28.2 degrees" equals the body-posture angle column; "airborne for 1.3 ± 0.7 x 10-3 s" is reproduced
  by no column (the airborne-time column gives 67 ± 26 ms).
- Spider (case pipeline): see README; the montage skips 1 frame in 13–14.

## Risks
- Real papers with video + scale + stated fps + per-event table are rare: impact rests on one hands-off paper unless
  S7 lands.
- Model variance: claim extraction differs between runs (17–23 claims); every claim is checked, but counts move.
- Plan call latency (~2 min of a ~4 min audit); SAM latency; the Space's 15 live runs/day cap → recorded runs default.
- Narrow overlap on the beetle verdict; the sensitivity range is printed (−1 % to +17 %).
- Montages not split by the agent; grid is the only scale route in the agent.
