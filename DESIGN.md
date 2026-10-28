# Audit agent — design (as built, 2026-10-28)

Origin: an agent council (7 members, a moderator and an evidence desk, external to this repo) followed by two
independent reviews of its plan (red-team, novelty-critic) and, after building, two reviews of the code (impact,
docs). Where the build departs from the council's plan, the reason is in `DECISIONS.md`.

## One sentence
Muse Spark reads the paper, its tables and its videos and **proposes**; code **checks every proposal**, measures every
number and returns, per claim and per video shot, an outcome with its evidence or a refusal naming the first failing
check. Every model output is a ledger row together with the check that accepted or rejected it.

## Flow (`pixels_to_proof/agent.py: run_audit`)
1. **Ingest (code).** Inventory of the bundle with SHA-256 hashes; PDF text (reading order and layout); tables to
   text; zips unpacked; scripts collected. The paper is the PDF that states a licence (longest text among those).
   **G0 licence:** no CC BY / CC0 / public-domain statement (dash variants normalised, NC/ND excluded) → stop; nothing
   is uploaded to the Model API, and the report says so.
2. **Shots and recordings.** Hard cuts and fades per video; shots shorter than `video.min_shot_frames` are
   transitions. **G2:** for every shot of at least three times that length, Muse Spark reads a contact sheet (tiles
   labelled with frame numbers) and proposes the separate recordings in it — a dissolve between two near-identical
   scenes is invisible to pixel statistics; code accepts a split only if the recordings lie in the shot, do not
   overlap and stay long enough after one tile is trimmed at each inner boundary. Muse Spark then reads every
   recording (in parallel) from its first frame (object box) and a frame at 40 % (overlay text typed in later):
   printed text, frame rate, scale reference. Framed montage panels are detected and logged; **the agent does not
   split montages yet** (the case-file pipeline does).
3. **Plan (Muse Spark, one call, strict JSON):** video labels and frame rates with quotes; the event table and the
   meaning and unit of every column (quantity types separate trajectory angle from body-posture angle); the meaning of
   any ± column (relative or absolute) with a quote; scale reference and size with a quote; object phrase; every
   kinematic claim with its quote, statistic, spread type and the column it summarises; the authors' speed method.
   **G1 (code):** quotes must occur in the PDF, scripts or transcribed video text (whitespace-insensitive; passages
   may be joined with "..."); frame-rate and grid-size quotes must state the number; a ± meaning needs a quote about
   it and a relative ± must be below 1; speed and trajectory columns must parse to SI units within plausible ranges.
   Rejected fields are dropped, never repaired by code.
4. **Re-proposal.** If G1 rejected a field the audit needs (frame-rate quote, ± meaning, grid size, authors' method,
   a claim quote), Muse Spark is called again with the checker's reasons; only the rejected fields are taken from
   the new answer (`plan.merge`); at most `plan.max_reproposals` rounds; the best-checked version is kept.
5. **Route per claim (code, `plan.needs`).** Statistics over events with a table column → TABLE CHECK
   (`tablecheck.py`: mean with sample SD, max, min, median, compared at the printed digits; if the proposed column fails,
   every other column of the same dimension is tried → MATCHES OTHER COLUMN; else NOT CHECKED with the closest values).
   A '±' of unknown type is read with the paper's own stated convention ("mean ± standard deviation") if it states one.
   A claim labelled single-event that equals a column statistic (≥ 2 significant digits) is routed to the table check.
   Units the agent cannot convert, or statistics without a column → refused with a reason.
6. **Per shot, before any tracking (G4):** an absolute take-off speed column must exist (else nothing to compare
   with); frame rate = Spark's reading only if that number is printed on the frame, else code parses the transcribed
   text, else the paper's rate for the file if unique; a printed "playback N x faster" means one video frame stands for
   N camera frames (a slower or non-integer factor refuses the shot); feasibility from the table's airborne times (the
   shot must be long enough to hold a flight; the flight must span `selfcheck.min_flight_frames` at this frame rate);
   scale = a grid measured by OpenCV (if Spark saw no grid, code accepts one only if ≥ 4 lines with < 2 % spacing
   spread), or the gap between the take-off platform and a landing platform or vertical target found on the shot's
   median frame; the size comes from the plan.
7. **Track (SAM 3.1, G5):** Spark's box, then the noun phrase, then up to two **box re-proposals** by Muse Spark given
   the rejection reason. Quality gate: no mask-area jump (object switch), real motion, track starts at rest.
8. **Measure and self-check (code):** skipped-frame repair (periodic only), ballistic fit, take-off at the parabola
   root, block bootstrap, interval widened by scale, frame-rate and gravity misfit in quadrature; gravity within
   `selfcheck.gravity_rel_tolerance`, sideways acceleration below `selfcheck.sideways_rel_tolerance`. The flight ends
   where the body falls back below its take-off height or where its horizontal motion stops (a raised target). When a
   check fails, the acceleration left after gravity is compared with the direction of motion; pointing against it
   (within 30°) is reported as the direction air drag would have — a direction, not a proof of drag. This diagnosis never
   changes a verdict.
9. **Blind pairing (code, G3):** trajectory geometry (angle, distance, height, end height, airborne time; right-to-left jumps
   mirrored) against every row; z-scored distance; the published speed is never used; accepted only if the best row is
   `pairing.min_margin` times closer than the runner-up.
10. **Verdict (code, G6):** the paired row's speed (finite, else CANNOT) ± its uncertainty (relative or absolute per
   the checked plan; if unknown, both readings — different verdicts → CANNOT MEASURE) against the measured interval.
   The ballistic estimate decides. If the authors' method is a smoothing spline with a stated parameter, an approximate
   scipy replica on our track is printed as a second reading (it does not vote). Each verdict also records the range of
   published values the measurement would have accepted.
11. **Ledger and receipt.** Every Muse Spark and SAM call (role, tokens, seconds, replayed-from-cache flag), every
   gate, every verdict; inputs' hashes; commit; `checks.toml` hash. Receipts are rendered for verdict shots. Any
   exception inside one shot refuses that shot only.

## Not done (known)
Montage panels in the agent; a flight model with air drag (tried, not adopted: see `DECISIONS.md`); a replica check on
the authors' raw points.
