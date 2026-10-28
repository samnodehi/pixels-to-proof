# Pixels to Proof

**An agent that audits the motion numbers in a scientific paper against the paper's own supplementary videos and
data.** Give it what the journal published — the PDF, the videos, the data tables, any analysis scripts — and it
returns an outcome for every kinematic claim in the PDF (recomputed from the paper's own table, or refused with a
reason) and a verdict for every video shot it can measure, against the matching row of the paper's data, or a
refusal that names the check that failed.

*The model proposes; tracking, arithmetic and physics decide. No number in a verdict is written by a language model.*

Built during the Meta Global AI Developer Hackathon (Oct 27 – Nov 4, 2026) with **Muse Spark 1.3** and **SAM 3.1**
(Meta Model API). Live app: the Hugging Face Space linked from the submission.

## What it does on real papers

### Larval beetles — Bertone et al. 2022, *PLOS ONE* 17(1): e0256509 (CC BY 4.0)
Input: the five files the journal publishes (PDF, two videos, an xlsx table, a zip with the authors' R script and raw
tracks). Nothing set by hand. Recorded run `beetle-20261028-49f237b` (clean commit, every model call made in the run,
392 s, 16 Muse Spark calls, 1 SAM 3.1 track):

- **19 kinematic claims** found in the PDF. Statistics over many jumps are recomputed from the paper's own event
  table (arithmetic only): 11 reproduce the printed digits (MATCHES TABLE); 2 are reproduced by a *different* column than
  the sentence suggests (e.g. "leaving the ground at an angle of 79.6 ± 28.2 degrees" equals the mean of the
  body-posture angle column, not of the trajectory angle column); 3 are reproduced by no column (NOT CHECKED — the
  aggregation behind a printed number is not always stated, so this is not a judgement of the paper); 3 are refused
  with a reason.
- **12 video shots** examined: 11 refused before any tracking, each for a stated reason (30 fps real-time footage — a
  jump spans about 3 frames; no measurable scale on the shot; a 60,000 fps shot covers 6.9 ms, shorter than any
  flight in the table); 1 tracked and measured.
- The measured jump was **paired blind** to its row of the event table: trajectory geometry only (angle, distance,
  height, airborne time), the published speed never looked at; row 488 is 4.9× closer than the runner-up.
- **Verdict for that row: REPRODUCED** — published 0.405 ± 0.024 m/s (the ± is the relative `VelError` column; the
  meaning comes from a quote in the authors' script), re-measured 0.436 m/s, interval 0.425–0.447; gravity from the
  flight 10.0 m/s²; sideways acceleration below 1 %. The overlap is narrow; the card also prints the range of published
  values this measurement would have accepted (0.401–0.475 m/s, −1 % to +17 %). The authors' stated estimator
  (smoothing spline, spar 1e-8, read from their Methods and script), approximately replicated on our track, gives
  0.398 m/s and is printed as a second reading.
- The plan is a proposal: in some runs gate G1 rejects a field (for example a quote that joins two sentences) and
  Muse Spark is asked again with the checker's reasons; only the rejected fields are taken from the re-proposal.

### Peacock spiders — Narendra et al. 2025, *J Exp Biol* 228: jeb249416 (CC BY 4.0; video CC BY 4.0, data CC0)
A different journal, data host and setup. Input: the article and supplementary PDFs, the Zenodo video, the Dryad CSV.
Recorded run `peacock-20261028-49f237b` (608 s, 9 Muse Spark calls including two plan re-proposals, 2 SAM 3.1
tracks):

- **The video**: cut and fade detection finds 3 shots; Muse Spark reads a contact sheet of each and proposes the separate
  recordings joined by dissolves (a male and a female jump to a vertical target; two magnified take-offs; a title card),
  which code checks (G2). The caption "Filmed at 5000 fps / Playback 4x faster" is read as one video frame = 4 camera
  frames (1/1250 s), which the gravity check then tests. The scale is the 4 cm gap from the take-off platform to the
  vertical target, stated in the paper and located on the image by code (1611 px).
- **Both full jumps: CANNOT MEASURE.** The flights are not ballistic: the male's fitted gravity is +21 % and it
  decelerates sideways at 25 % of its vertical acceleration; the female's +11 % and 11 %. For the male the extra acceleration points within
  11° of straight against the motion, the direction air drag would have on a 2–13 mg spider, and the refusal says so
  (for the female it is 31°, outside the 30° the diagnosis uses). Blind pairing (take-off
  angle, peak and end height of the trajectory) was not unambiguous either. The magnified take-offs show no landing
  target, so no gap can be measured: refused.
- **24 claims** from the paper and from the captions printed on the video, checked against the rows of the right sex:
  5 reproduce the printed digits — among them both mean take-off angles, which reproduce only as *circular* means, as
  the paper's statistics are; 5 are NOT CHECKED, three of them because the printed number is the table value
  *truncated* rather than rounded (e.g. the caption's male mean peak acceleration 127.871 printed as 127.8); 14 refused
  (leg timings have no table column; one animal's take-off duration or acceleration is not measurable from a centroid
  track; two caption values in g units are not convertible; the 4 cm platform distance and a 0.4–60 ms behaviour range
  are not kinematic results). The plan was re-proposed twice for five rejected claim quotes; neither re-proposal gave
  quotes that pass, so the first plan was kept and those five claims were dropped (all in the ledger).
- Claim extraction varies between runs: in an earlier run the male body mass "4.94 ± 1.86 mg, n = 10"
  was extracted and reproduced only as a mean over spiders (each spider's jumps averaged first, n = 10 spiders), while
  the female "10.40 ± 2.05 mg, n = 12" gave 10.43 ± 2.05 and stayed NOT CHECKED.

### Breadth: 11 more papers, one run each (`showcase/breadth.md`, app tab "Breadth")
Ten PLOS papers with raw data on Zenodo (sprinting and jumping athletes, fish, ants, guinea fowl, pigeons, tadpoles) and
the *Phidippus regius* jumping-spider paper (Sci Rep 2018). 276 claims: 45 reproduced to the printed digits, 114 NOT
CHECKED (mostly tables the agent cannot read as laid out, or values that describe another aggregation; three are the
table value truncated), 117 refused with a reason. Examples of what the code-side checks add: sprint times reproduced
per training group although the plan named no group (the code found the subset); a body mass "73.23 ± 6.82 kg" that is
the table's 73.2333 ± 6.8290 truncated.

## How it works

| step | who | what is checked by code |
|---|---|---|
| licence gate | code | an open licence (CC BY / CC0 / public domain) must be stated in the PDF before anything is uploaded |
| inventory | code | shots by cut and fade detection; tables to text; archives unpacked |
| recordings | **Muse Spark** (contact sheet) | separate recordings inside a shot (joined by dissolves); each must lie in the shot, not overlap and be long enough |
| read each shot | **Muse Spark** (two frames) | printed frame rate and playback speed, scale reference, object box — the frame rate is kept only if the number is printed on the frame; otherwise code parses the printed text |
| plan | **Muse Spark** (PDF + table digests + scripts) | file roles, the meaning and unit of every table column, every claim with its quote, the authors' speed method. Each quote must occur in the PDF, scripts or video text; frame-rate and scale quotes must state the number; the speed and trajectory columns must parse to SI units within a plausible range. A rejected field the audit needs triggers a **re-proposal** by Muse Spark with the checker's reasons (at most 2) |
| route | code | statistics over many jumps → table check (arithmetic, on the rows of the subset the claim covers; circular or per-animal statistics when the paper uses them); single jumps → video; anything else refused |
| feasibility | code | frame rate and scale (grid, or platform-to-target gap) present; flight long enough at this frame rate; shot long enough to contain a flight |
| track | **SAM 3.1** | quality gate (no object switch, real motion, track starts at rest, flight not cut by the shot's end); on rejection the next prompt, then **Muse Spark re-proposes the box** with the rejection reason |
| measure | code | ballistic fit from take-off to landing (or to impact on a raised target), take-off at the parabola root, block bootstrap; skipped frames from video editing detected and re-inserted |
| self-checks | code | gravity from the flight within 10 % of 9.81 m/s²; sideways acceleration below 10 % of vertical |
| pair | code | blind: trajectory geometry vs every table row, margin ≥ 2× |
| verdict | code | published value ± its stated uncertainty overlaps the measured interval → REPRODUCED; outside → NOT REPRODUCED; any failed check → CANNOT MEASURE. A ± whose meaning (relative or absolute) is not established is evaluated both ways; if the verdicts differ → CANNOT MEASURE |

Every model output (Muse Spark and SAM 3.1) and every check is written to a **run ledger** (`ledger.json`) with
tokens, timings and the gate that accepted or rejected it; the app renders runs from ledgers. Each stage is cached in
the run folder; a re-run in the same folder replays cached model outputs and the ledger marks them as replayed. The
main thresholds are in `checks.toml`, whose hash is in every ledger. Design and its history: `DESIGN.md`,
`DECISIONS.md`.

## Evidence that the checks work

- **Synthetic calibration of the measuring core** (`bench/RESULTS_seed2026.md`; runs through the case-file pipeline,
  not the agent's planning): 48 rendered high-speed videos with known truth and planted claim errors. Median speed
  error 0.05 %; 0 of 12 true claims flagged; planted errors of 5 %, 10 % and 20 % flagged in 23 of 24 cases (the 24th
  refused); 4 of 4 wrong frame rates refused by the gravity check. After the latest changes the kinematics were recomputed from the cached tracks: identical.
- **Fault injection on the agent** (`bench/faults.py`, results on the app's Calibration tab): one model proposal at a
  time is corrupted the way a wrong model answer would be (wrong column map, wrong units, misread numbers, wrong frame
  rate, a box on the background, …) and the agent is re-run; the table reports what caught it, what recovered and
  whether any verdict went wrong. Re-proposals in these runs are live model calls, so repeat runs can differ.
- **A refusal on real data** (case-file pipeline, hand-prepared: frame range, panel and platform-gap scale set by hand;
  the agent does not yet split montages): jumping spider (Nabawy et al. 2018, *Sci Rep* 8:7142, CC BY 4.0), "Level
  jumps" montage. At the stated 3,200 fps the flight curves at +27 to +42 % of gravity and decelerates sideways; the
  montage also skips one frame in every 13–14, which the code detects. All three jumps: CANNOT MEASURE.

## Limits (stated, not hidden)

- Two papers audited hands-off with their videos, one video verdict (REPRODUCED) among them; real papers with a
  high-speed video, a visible scale, a stated frame rate and a per-event table are rare (two searches over ~70 papers
  found no third), and small animals can be slowed by air drag. Table checks reach many more papers (breadth test).
- The agent measures scale from a grid or a platform gap and treats a montage shot as one picture (montage panels
  exist only in the case-file pipeline).
- Passing the self-checks shows the flight is physically consistent; it does not prove the number exact. The tracked
  point is the mask centroid, not the centre of mass.
- REPRODUCED means "consistent within the combined uncertainty", not equal; each card prints the range of published
  values the measurement would have accepted (on the beetle: −1 % to +17 %, so it is lenient on the high side).
- Only free ballistic flight in the image plane is measured; refusals name the reason. Claim extraction by the model
  varies between runs (18 to 23 claims on the beetle, 24 to 28 on the peacock spider across our runs); every extracted claim is checked by code.

## Run it

    pip install -r requirements.txt          # needs ffmpeg and pdftotext (poppler) on the system
    export MODEL_API_KEY=...                 # Meta Model API key (or P2P_SECRETS=/path/to/file with MODEL_API_KEY=...)
    python -c "from pathlib import Path; from pixels_to_proof import agent; agent.run_audit(Path('BUNDLE_DIR'), Path('runs/x'))"
    python app.py                            # the web app (reads showcase/audits/*; live re-runs need bundles/<name>/)
    python -m bench.run CASES --out DIR      # synthetic calibration (cases from python -m bench.generate)
    python -m bench.faults BUNDLE BASE_RUN --out DIR   # fault injection (live model calls)

`BUNDLE_DIR` holds the paper's files as downloaded from the publisher. Only openly licensed material is processed.
A run writes `report.json`, `ledger.json`, `plan_checked.json` and `units/<shot>/` (clip, track, receipt).
`python -m pixels_to_proof case.json` runs the older case-file pipeline. Python ≥ 3.11; ffmpeg and pdftotext needed.

## Licences

Code: MIT. Paper media shown in the app are CC BY 4.0 and credited where shown. The SAM streaming adapter follows
Meta's cookbook example (MIT); see `NOTICE`.
