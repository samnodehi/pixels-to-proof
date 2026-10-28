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
