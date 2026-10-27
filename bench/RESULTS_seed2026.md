# Synthetic calibration results

Cases: 48; pipeline errors: 0

## Measurement accuracy (cases with the correct frame rate)
- |measured - true| / true: median 0.05%, 90th percentile 0.22%, max 0.61%
- true value inside the reported interval: 41/43
- Muse Spark read the frame rate from the overlay correctly: 43/43
- object followed via Muse Spark's box: 43/43; cases where a track was rejected by the quality check and another prompt used: 0

## Verdicts

| group | n | expected | REPRODUCED | NOT REPRODUCED | CANNOT MEASURE | ERROR |
|---|---|---|---|---|---|---|
| planted error 0% | 12 | REPRODUCED | 12 | 0 | 0 | 0 |
| planted error 1% | 8 | NOT REPRODUCED | 2 | 6 | 0 | 0 |
| planted error 10% | 8 | NOT REPRODUCED | 0 | 8 | 0 | 0 |
| planted error 20% | 8 | NOT REPRODUCED | 0 | 7 | 1 | 0 |
| planted error 5% | 8 | NOT REPRODUCED | 0 | 8 | 0 | 0 |
| wrong frame rate in case | 4 | CANNOT MEASURE | 0 | 0 | 4 | 0 |
