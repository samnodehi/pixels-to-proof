# Decisions and rule history

Dated record of choices that affect verdicts, including those made after seeing data. Thresholds live in `checks.toml`.

## 2026-10-27
- D1 The model never supplies a final number; tracking and code measure (Day-1: Muse Spark's grid estimate was 7 % off).
- D5 Primary speed estimate = ballistic fit of the flight (validated by the gravity check).
- Gravity self-check: fitted g within 10 % of 9.81 m/s² (set before any real-paper run).
- Free-flight self-check: sideways / vertical acceleration below 10 % (set while analysing the spider montage; the
  synthetic set and the beetle stay below 0.7 %, the spider level jumps are at 31–69 %).
- Skipped-frame repair only for periodic long steps (≥ 3 on one period): a first version without the periodicity test
  made false repairs on 9 synthetic tracks; the benchmark re-run with the final version is identical to the committed one.

## 2026-10-28 (agent council, then two independent reviews)
- Hands-off audit agent replaces hand-written case files. Muse Spark proposes, code checks every field (DESIGN.md).
- **Verdict estimator.** The council first voted for two voting estimators (ballistic + the authors' method when its
  replica is validated). Reviews pointed out that this produced METHOD-DEPENDENT labels that alternate across edited
  claims and needed a validation gate with thresholds chosen after seeing 9 tracks of one paper. Decision: the
  ballistic fit decides; the authors' estimator, replicated when the paper states it and it can be coded, is printed as
  a second reading. History: our earlier "spline method" number (0.360 on the beetle) was our own noise-tied spline, not
  the authors' method; the authors' smoothing P-spline replicated in scipy gives 0.401 on their own track for jump 488
  (published 0.405) and 0.398 on ours.
- **Pairing margin** `min_margin = 2.0` was chosen after the beetle pairing margin (≈5×) was known; no other real
  pairing existed at the time.
- **Uncertainty of unknown meaning.** If a ± column's meaning (relative or absolute) is not supported by a verbatim
  quote, both readings are evaluated; if they give different verdicts the result is CANNOT MEASURE (found by fault
  injection: the stricter no-± reading had turned the beetle verdict into NOT REPRODUCED).
- **Track must start at rest.** Found by fault injection: with Spark's box replaced by a background box, the text
  prompt tracked the larva only from frame 97, after take-off; the gravity check passed but the geometry was wrong (the
  blind pairing refused it). The quality gate now rejects tracks that begin with the object already moving.
- **Frame rate.** Spark's reading of the printed rate is kept only if the number appears in the text it transcribed;
  otherwise code parses the transcribed text itself (a single rate on a line saying captured/recorded/filmed).
- **Statistic label.** A claim labelled as a single event whose value equals the mean, max or min of its table column
  is routed to the table check (code overrides the label).
- **Plan re-proposal merge.** A re-proposal may only replace the fields the checker rejected; everything already
  accepted is kept (re-proposals had changed unrelated claims, which made runs harder to compare).
- **'±' convention.** When the plan leaves a claim's spread type unknown and the paper states "mean ± standard
  deviation" (or SD/SE) somewhere, that convention is applied; otherwise the claim is NOT CHECKED.

## 2026-10-28 afternoon (after the impact and documentation reviews)
- Hardening: finite published values only; a single take-off speed column (several → ambiguous); quotes for frame
  rate and grid size must state the number; the ± meaning needs a quote about it and a relative ± must be below 1; the
  speed column must be 0.01–30 m/s; table checks fail closed when the printed number is not found; licence check on
  normalised dashes; one shot's failure does not abort the audit; nothing is tracked when there is nothing to compare
  with; right-to-left jumps mirrored for pairing.
- Track-start gate: compared with the flight's own speed (median-filtered maximum step), not the 90th percentile of all
  steps, which rejected short flights in long clips.
- Verdict tolerances and track thresholds are read from `checks.toml`; dead keys removed.
- Each verdict records the published-value range it would accept (sensitivity), replacing an unsupported "15 % / 20 %"
  sentence in the README.

## 2026-10-28 evening (second paper: peacock spider, J Exp Biol 2025)
Changes made while preparing the second hands-off bundle. `kinematics` was recomputed on every cached track before and
after: none of the 48 synthetic tracks, the beetle track or the three hand-prepared spider panels changed, and a fresh
hands-off beetle run gives the same verdict.
- **Fades.** Shots are also split at gradual transitions (most of the picture changes and its mean brightness moves
  across a 20-frame window). Spans that contain a hard cut, or are shorter than the window, are left to the cut
  detector, so the beetle videos keep exactly their old shots.
- **Recordings inside a shot (G2).** A dissolve between two near-identical scenes (same platform, same target, a
  different spider) is invisible to pixel statistics (2–5 % of pixels change, as during a flight). Muse Spark therefore
  reads a contact sheet of every shot of at least 90 frames and proposes the separate recordings; code accepts a split
  only if the recordings lie inside the shot, do not overlap and are at least `video.min_shot_frames` long. A single
  recording leaves the shot unchanged; none (a title card) leaves it whole, and it is not tracked if the frame reading
  also finds no object. First version trimmed one tile at each inner boundary; in the first peacock run Spark widened
  the transition by about 60 frames and the trimmed male recording ended mid-flight. Boundaries are now placed in the
  middle of each proposed transition, and a track that ends while the object is still in the air is refused (G5: the
  shot ends before the flight does) instead of being measured on a partial flight.
- **Scale sanity.** A platform must protrude from the image border (its tip more than 1 % of the width inside): in the
  first peacock run a black title card and the magnified take-off shots, where no landing target is visible, returned
  a "gap" spanning the whole frame.
- **Quotes across a hyphenated line break.** "take-off" broken at a line end extracts as "takeoff"; quotes are compared
  with hyphens between letters removed on both sides (re-checking a cached beetle plan gives the same results).
- **Overlay text from two frames.** Captions are often typed in after the first frame; the frame reading now gets the
  first frame (for the object box) and a frame at 40 % of the shot (for the text).
- **Playback speed.** "Playback N x faster" printed on a shot means one video frame stands for N camera frames; a
  slower or non-integer factor refuses the shot. The gravity self-check tests the reading independently (a wrong N
  scales g by N²).
- **Scale from a gap to a vertical target.** `scale.platform_gap` now recognises a vertical landing target at the
  border (a straight edge over ≥ 40 % of the height with a darker solid body behind it) besides a second platform. The
  three hand-prepared spider panels still give their old gaps.
- **End of flight.** A flight also ends when the horizontal motion stops (three frames below 35 % of the early-flight
  horizontal step, and the next eight frames below it on average): a landing on a raised target never brings the body
  back below the take-off height. The rule is skipped when the early horizontal step is below ten times the track's
  horizontal jitter (near-vertical jumps; found by the impact review, which showed a first version truncating noisy
  near-vertical flights). The jump height is now the maximum inside the flight window.
- **End height** (height at the end of the flight) is a pairing quantity, for tables that report it.
- **Direction of the extra acceleration (diagnostic, no effect on verdicts).** When a self-check fails and the flight
  decelerates sideways by at least 5 % of g, the acceleration left after removing gravity is compared with the
  direction of motion; within 30° of straight against it, the refusal says so ("the direction air drag would have").
  This is a direction, not a proof of drag: a wrong scale or frame rate rescales only the vertical acceleration. A drag
  model was tried on the first peacock track and not adopted: g and the drag constant trade off against each other, so
  the take-off speed it returns is not constrained.
- Not changed, on purpose: a split keeps the outer ends of a shot as they are (only inner boundaries are trimmed), so a
  shot that Spark calls one recording is never shortened.
- **Table checks on the second paper.** Its statistics are mostly per sex, per animal or circular, which the first
  version could not express (every such claim came out NOT CHECKED):
  - *Subset of rows:* Muse Spark proposes the column and cell value that select the events a claim covers (e.g.
    sex = male); code accepts the filter only if that value occurs in that column, else the claim is checked against
    all rows.
  - *Circular statistics:* when the paper states them (code finds "mean vector", "circular mean", "Watson–Williams"
    or "Rayleigh test" in the PDF), a mean angle that arithmetic does not reproduce is also tried as a circular mean
    with circular SD sqrt(−2 ln R). On the peacock paper both sexes' take-off angles then reproduce to the printed digits.
  - *Per-animal statistics:* when a claim states its n and n is not the number of rows, each animal's rows are averaged
    first; the animal is the animal-id column alone or with one categorical column (IDs are reused across conditions),
    and a grouping is used only if it yields exactly the stated n. Male mass (n = 10 spiders) then reproduces; female
    mass (n = 12) gives 10.43 ± 2.05 against the printed 10.40 ± 2.05 and stays NOT CHECKED.
  - *Statistic label:* the statistic is Spark's proposal too ("a maximum acceleration of 122.7" is the mean of the
    per-jump peak accelerations). If the proposed statistic fails on the named column, the others are tried there,
    only for values printed with at least three significant digits; a match says which statistic reproduced it.
  - *Truncation:* a value that a statistic of the named column reproduces only when truncated instead of rounded is
    reported as such (90.069 printed as 90.06; 127.871 printed as 127.8); the outcome stays NOT CHECKED.
  - *Recording starts:* a recording created by a split starts at the first frame Spark gives for it (not inside the
    dissolve, where the first frame is a blend and the box can land on a ghost) and still ends in the middle of the
    following transition.
  - *Captions:* claims printed on the videos are proposed too (quoted from the transcribed overlay text) and marked as
    such in the report. A single-event claim that no measured shot was paired to ends as NOT CHECKED, not "see video".
