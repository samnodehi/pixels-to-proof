# Audit agent — design (2026-10-28)

Source: agent council (council/room1/RESULT.md, 7/7 vote for plan "Verified Auditor") plus two independent reviews
(red-team, novelty-critic) of that plan. This file records what is built; where it departs from the council result,
the reason is given.

## One sentence
Muse Spark reads the paper, its tables and its videos and **proposes**; code **checks every proposal**, measures every
number and returns, per claim, a verdict with evidence or a refusal naming the first failing check. Every model output is
a row in a ledger with the check that accepted or rejected it.

## Flow
1. **Ingest (code).** Inventory of the bundle; PDF text; tables to text; zip contents listed; **licence gate G0**: no
   CC BY / CC0 / public-domain statement in the PDF → nothing is uploaded to the Model API.
2. **Video inventory.** Shots by cut detection (code). Montages: Spark watches the whole video and returns sections and
   panel labels; code finds panel rectangles (coloured borders) and keeps a panel only where both agree. Per shot/panel
   Spark reads a frame: printed frame rate, scale reference, object box.
3. **Plan (Spark, one call, strict JSON).** File roles; meaning and unit of every table column (including what a ±
   column means, with the quote or script line that says so); the per-event table and its id column; claims from the
   PDF with exact quotes, whether each is an aggregate over n events; the authors' speed estimator with its quote.
   **G1 (code):** every quote must occur in the PDF/script text (normalised whitespace), units must parse, named columns
   must exist, values must lie in the column's range. A ± whose meaning has no supporting quote is set to UNKNOWN
   (the verdict then uses no ±, the stricter reading) — never guessed (red-team #2).
4. **Route per claim (code, needs-matrix).** Aggregate claims (mean ± SD over n) → TABLE CHECK (arithmetic on the
   column the plan named, sample SD, compare at printed digits; MATCHES TABLE or NOT CHECKED with the closest value; no
   "differs" label). Single-event rows of the per-event table → VIDEO route via pairing. Anything else → refuse with a
   reason from a fixed vocabulary.
5. **Per shot/panel inputs (code) before pairing** (red-team #1): frame rate (case ▸ overlay ▸ the plan's per-video
   value) and scale (grid ▸ platform gap). A shot without both is CANNOT for the reason named, and is not paired.
6. **Track (SAM 3.1)** from Spark's box, text prompt as fallback; quality gate; flight window; kinematics; two
   self-checks (gravity within 10%, sideways acceleration below 10% of vertical); too-short flights refused.
7. **Blind pairing (code).** Event geometry (angle, distance, height, airborne time) against every row of the
   per-event table; the claimed speed is never used. Accept only if best/second-best distance ≥ margin threshold.
8. **Re-proposal (Spark) on rejection.** When a gate rejects a proposal (panel, prompt, column map), Spark is called
   again with the rejection reason — never with the claimed value — and proposes the next candidate. Bounded (2), every
   round logged as plan_version v1 → v2. This is what makes the loop an agent and not a fixed pipeline; its effect is
   measured by fault injection (caught k/N, recovered to the unmutated verdict r/k, recovered to a wrong verdict: must
   be 0). Departure from the council result: the council kept recovery inside code only; reviewers noted that this
   leaves no agentic behaviour to show.
9. **Verdict (code).** Ballistic estimate decides. The authors' estimator, when the paper states it and it can be
   coded (beetle: smoothing P-spline), is replicated and printed as a second reading together with its check on the
   authors' own raw points; it does not vote. Departure from the council's two-estimator vote: the vote produced
   METHOD-DEPENDENT zigzags across edited claims and needed a gate with thresholds set after viewing n=9 tracks
   (novelty-critic #1, red-team #4).
10. **Ledger.** One JSON per run: inputs and their hashes, commit, every model call (role, tokens, seconds, accepted or
   rejected by which gate), every gate result, per-claim verdict. The app renders runs from ledgers (replay) and
   labels live runs.

## Thresholds
`checks.toml`, committed before final runs; its hash is written into every ledger.
