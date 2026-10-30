# Freeze check (2026-10-30)

The recorded runs shown in the app and the demo video are from commit `49f237b` (beetle, peacock spider, fault
injection) and `7cf697a` (breadth). Before submission both hands-off papers and the fault injection were run again on
the final code, to see whether the results hold and what varies. Runs: `showcase/freeze/` (reports and ledgers) and
`showcase/freeze/faults_32dbbf4.md`.

## Final code (`32dbbf4`)

| | recorded run (`49f237b`) | freeze run (`32dbbf4`) |
|---|---|---|
| beetle video verdict | REPRODUCED 0.436 [0.425–0.447], row 488 | REPRODUCED 0.436 [0.425–0.446], row 488 |
| beetle claims | 19: 11 MATCHES TABLE, 2 other column, 3 NOT CHECKED, 3 REFUSED | 21: 15 MATCHES TABLE, 2 NOT CHECKED, 4 REFUSED |
| peacock jumps | both CANNOT MEASURE (gravity +21 % / +11 %) | both CANNOT MEASURE (gravity +21 % / +11 %) |
| peacock claims | 24: 5 MATCHES TABLE, 5 NOT CHECKED, 14 REFUSED | 29: 8 MATCHES TABLE, 7 NOT CHECKED, 14 REFUSED |
| fault injection (12 kinds) | caught 4, recovered 6, no effect 2, wrong 0 | caught 6, recovered 4, no effect 2, wrong 0 |

- **Every claim found in both runs got the same outcome** (beetle 16 common claims, peacock 21), except two beetle
  claims ("79.6 ± 28.2 degrees", "7.9 ± 4.3 mm") that moved from MATCHES OTHER COLUMN to MATCHES TABLE: in the freeze
  run Muse Spark proposed the body-posture and height columns for them directly, the columns the recorded run had
  found by code.
- The number of claims extracted varies between runs (a stated limit); the counts in the video and README are those
  of the recorded runs.
- In the fault table, "caught" vs "recovered" moves between runs because re-proposals are live model calls that may
  add or drop claims; no corrupted answer produced a wrong verdict in any run.

## Two defects found on the way, and fixed

1. **Over-split recording** (run on `c082d1b`): Muse Spark split the continuous beetle recording into six; the flight
   ran past a proposed boundary and the REPRODUCED jump was lost (all shots refused, no wrong verdict). Fix: a flight
   still under way at a Spark-proposed boundary sends the recording back to be measured joined with the next one,
   kept only if that gives a measured flight. Replaying that run: recordings 1–4 joined, REPRODUCED, same numbers.
2. **Duplicate claim after a re-proposal** (run on `1d492b3`): a re-proposal stated "5.5 x 10-3 s" in ms, both copies
   were kept, and the fault classifier read the copy as a changed verdict ("WRONG 1"). Fix: claims are compared by
   quantity, statistic, value and ± in SI units, in the merge and in the classifier.

Details: `DECISIONS.md`, section 2026-10-30.
