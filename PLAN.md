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
(G0 licence → shots, G2 recordings (Spark split) + frame reads → plan with G1 and re-proposal → routing → table check → G4 inputs → SAM track with
G5 and box re-proposal → self-checks → G3 blind pairing → G6 verdict → ledger and receipt). The older case-file
pipeline (`pipeline.py`, `cases/`) remains for the synthetic benchmark and the hand-prepared spider montage case.

## Stages
- S0 Day-1 spike: DONE 2026-10-27 (beetle jump re-measured from a hand-prepared case).
- S1 Measuring core + CLI + tests: DONE 2026-10-27.
- S2 Synthetic calibration: DONE 2026-10-27 (`bench/RESULTS_seed2026.md`); full re-run identical on 2026-10-28
  (morning); after the later changes to the measuring code the kinematics were recomputed from the cached tracks:
  identical.
- S3 Spider montage (hand-prepared cases): DONE 2026-10-27, all CANNOT MEASURE with reasons.
- S4 Web app + Space: DONE 2026-10-27; replaced 2026-10-28 by the ledger-driven Audit view (recorded runs, labelled
  live re-run of bundled papers, rate limited; no uploads).
- S5 Audit agent, hands-off on the beetle bundle: DONE 2026-10-28 (council → reviews → build → impact/doc review →
  hardening). Recorded run now `beetle-20261028-49f237b` (re-recorded with S7).
- S6 Fault injection: DONE 2026-10-28; re-run on the recorded beetle run of commit 49f237b (12 faults: caught 4,
  recovered 6, no effect 2, wrong 0, errors 0; `showcase/faults.md`). Re-run at freeze.
- S7 Second hands-off paper: DONE 2026-10-28 — peacock spider (J Exp Biol 2025; Zenodo video, Dryad CSV, files fetched
  by Sam). New agent abilities: fades, Spark-proposed recordings (G2), playback speed-up, gap-to-target scale, wall
  landing, truncated-flight refusal, per-subset / circular / per-animal table statistics, truncation notes. Recorded
  run `peacock-20261028-49f237b`; beetle re-recorded on the same commit (`beetle-20261028-49f237b`, same verdict).
  Phidippus (Sci Rep 2018) main PDF now available: a third hands-off bundle needs montage splitting (not built).
- S7b Breadth: DONE 2026-10-28 night — 11 more papers hands-off (10 PLOS + Zenodo data, Phidippus): 276 claims, 45
  reproduced, 114 NOT CHECKED, 117 refused (`showcase/breadth.md`). Video hunt (two searches, ~30 more papers): no
  third video paper meets all requirements; best near-miss = glass katydids (iScience 2025; video on PMC, data on
  GitHub without a licence).
- S8 Demo video (3 min, English AI voice "daniel", captions), README, submission: Nov 1–3; public repo and Space only
  with Sam's OK.
  Progress 2026-10-29: script v3 approved; narration (2:52) and captions approved by Sam; first cut of the video
  rendered from the recorded runs (`demo/video/`), waiting for Sam's review.

## Findings so far
- Beetle (agent, hands-off): 19 claims — 11 reproduced from the table, 2 by another column, 3 by no column, 3 refused;
  12 shots — 11 refused before tracking with reasons, 1 measured; blind pairing row 488 (4.9×); REPRODUCED
  0.405 ± 0.024 vs 0.436 [0.425–0.447]; authors' method replica 0.398 (second reading). Scale: our grid 5.0 mm vs the
  authors' implied 4.85 mm from their raw tracks (3 %; earlier analysis, not in the ledger).
- Beetle text vs table (not findings about the authors; aggregation is not always stated): "leaving the ground at an
  angle of 79.6 ± 28.2 degrees" equals the body-posture angle column; "airborne for 1.3 ± 0.7 x 10-3 s" is reproduced
  by no column (the airborne-time column gives 67 ± 26 ms).
- Peacock spider (agent, hands-off): both full jumps refused — not ballistic (male g +21 %, sideways 25 %; female
  +11 %, 11 %), residual acceleration against the motion; take-off angles reproduce only as circular means; three
  printed values are the table values truncated (90.069 → 90.06, 0.9872 → 0.98, 127.871 → 127.8); male mass
  reproduces per spider (n = 10), female mass gives 10.43 vs the printed 10.40 (earlier run).
- Spider (case pipeline): see README; the montage skips 1 frame in 13–14.

## Risks
- Real papers with video + scale + stated fps + per-event table are rare: two hands-off papers, one verdict among them.
- Model variance: claim extraction differs between runs (beetle 18–23, peacock 24–28 claims); every claim is checked, but counts move.
- Plan call latency (80–100 s per plan version; recorded audits 392 s and 608 s with re-proposals); SAM latency; the Space's 15 live runs/day cap → recorded runs default.
- Narrow overlap on the beetle verdict; the sensitivity range is printed (−1 % to +17 %).
- Montages not split by the agent. Small animals can be slowed by drag (peacock spider): the ballistic model then
  refuses.
