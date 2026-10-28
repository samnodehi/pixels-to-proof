# Pixels to Proof

**An agent that audits the motion numbers in a scientific paper against the paper's own supplementary videos and
data.** Give it what the journal published — the PDF, the videos, the data tables, any analysis scripts — and it
returns, for every kinematic claim, a verdict with its evidence or a refusal that names the check that failed.

*The model proposes; tracking, arithmetic and physics decide. No number in a verdict is written by a language model.*

Built during the Meta Global AI Developer Hackathon (Oct 27 – Nov 4, 2026) with **Muse Spark 1.3** and **SAM 3.1**
(Meta Model API). Live app: the Hugging Face Space linked from the submission.

## What it does on a real paper

Bertone et al. 2022, *PLOS ONE* 17(1): e0256509 (larval beetle jumps, CC BY 4.0). Input: the five files the journal
publishes (PDF, two videos, an xlsx table, a zip with the authors' R script and raw tracks). Nothing set by hand.

- **19 kinematic claims** found in the PDF and routed by code:
  11 recomputed exactly from the paper's own event table (MATCHES TABLE), 2 reproduced by a *different* column than
  the sentence suggests (e.g. "leaving the ground at an angle of 79.6 ± 28.2°" equals the mean of the body-posture
  angle column, not of the trajectory angle column), 4 not reproducible from any column (NOT CHECKED — the aggregation
  behind a printed number is not always stated), 2 refused with a reason.
- **12 video shots** examined: 11 refused before any tracking, each for a stated reason (30 fps real-time footage —
  a jump spans at most 3 frames; no measurable scale on the shot; a 60,000 fps shot covers 6.9 ms, shorter than any
  flight in the table); 1 measured.
- The measured jump was **paired blind** to its table row: trajectory geometry only (angle, distance, height, airborne
  time), the published speed never looked at; row 488 is ~5× closer than the runner-up.
- **Verdict: REPRODUCED** — published 0.405 ± 0.024 m/s (the ± is the relative `VelError` column; Muse Spark found the
  script line that makes it relative), re-measured 0.436 m/s, interval 0.425–0.447, gravity from the flight 10.02 m/s²,
  sideways acceleration 0.7 %. The authors' own estimator (smoothing spline, spar 1e-8, read from their Methods and
  script) replicated on our track gives 0.398 m/s, printed as a second reading.

## How it works

| step | who | what is checked by code |
|---|---|---|
| licence gate | code | an open licence (CC BY / CC0 / public domain) must be stated in the PDF before anything is uploaded |
| inventory | code | shots by cut detection; tables to text; archives unpacked |
| read each shot | **Muse Spark** (image) | printed frame rate, scale reference, object box — the frame rate is kept only if the number is printed on the frame; otherwise code parses the printed text |
| plan | **Muse Spark** (PDF + table digests + scripts) | file roles, the meaning and unit of every table column with a verbatim quote, every claim with its quote, the authors' speed method. Each quote must occur in the files; units must parse; values must lie in the column's range |
| route | code | statistics over many jumps → table check (arithmetic); single jumps → video; anything else refused |
| feasibility | code | frame rate and scale present; flight long enough at this frame rate; shot long enough to contain a flight |
| track | **SAM 3.1** | quality gate (no object switch, real motion, track starts at rest); on rejection the next prompt, then **Muse Spark re-proposes the box** with the rejection reason |
| measure | code | ballistic fit, take-off at the parabola root, block bootstrap; skipped frames from video editing detected and re-inserted |
| self-checks | code | gravity from the flight within 10 % of 9.81 m/s²; sideways acceleration below 10 % of vertical |
| pair | code | blind: trajectory geometry vs every table row, margin ≥ 2× |
| verdict | code | published value ± its stated uncertainty overlaps the measured interval → REPRODUCED; outside → NOT REPRODUCED; any failed check → CANNOT MEASURE |

Every model output and every check is written to a **run ledger** (`ledger.json`) with tokens, timings and the gate
that accepted or rejected it; the app renders runs from ledgers. All thresholds are in `checks.toml`, whose hash is in
every ledger. Design and its history: `DESIGN.md`, `DECISIONS.md`.

## Evidence that the checks work

- **Synthetic calibration** (`bench/RESULTS_seed2026.md`): 48 rendered high-speed videos with known truth and planted
  claim errors. Median speed error 0.05 %; 0 of 12 true claims flagged; planted errors of 5 %, 10 % and 20 % flagged in
  23 of 24 cases (the 24th refused); 4 of 4 wrong frame rates refused by the gravity check.
- **Fault injection** (`bench/faults.py`, `showcase/faults.md`): single corrupted model proposals (wrong column map,
  wrong units, misread numbers, wrong frame rate, a box on the background, …) on the beetle bundle; each is caught by a
  check, recovered from, or has no effect — the count of wrong verdicts is reported.
- **A refusal on real data**: jumping spider (Nabawy et al. 2018, *Sci Rep* 8:7142, CC BY 4.0), "Level jumps" montage:
  at the stated 3,200 fps the flight curves at +27 to +42 % of gravity and decelerates sideways; the montage also skips
  one frame in every 13–14, which the agent detects. It returns CANNOT MEASURE for all three jumps.

## Limits (stated, not hidden)

- One paper audited hands-off so far; real papers with a high-speed video, a visible scale, a stated frame rate and a
  per-event table are rare.
- Passing the self-checks shows the flight is physically consistent; it does not prove the number exact. The tracked
  point is the mask centroid, not the centre of mass.
- REPRODUCED means "consistent within the combined uncertainty", not equal. On the beetle clip, an edited claim is
  separated only when it is about 15 % below or 20 % above the published value.
- Only free ballistic flight in the image plane is measured; refusals name the reason.

## Run it

    pip install -r requirements.txt          # needs ffmpeg and pdftotext (poppler) on the system
    export MODEL_API_KEY=...                 # Meta Model API key (or P2P_SECRETS=/path/to/file with MODEL_API_KEY=...)
    python -c "from pathlib import Path; from pixels_to_proof import agent; agent.run_audit(Path('BUNDLE_DIR'), Path('runs/x'))"
    python app.py                            # the web app

`BUNDLE_DIR` holds the paper's files as downloaded from the publisher. Only openly licensed material is processed.

## Licences

Code: MIT. Paper media shown in the app are CC BY 4.0 and credited where shown. The SAM streaming adapter follows
Meta's cookbook example (MIT); see `NOTICE`.
