# Pixels to Proof - project plan

Meta Global AI Developer Hackathon, Indie track. Build window 2026-10-27 .. 2026-11-04 21:00 ET.
All work in this repository was written during the hackathon.

## Objective
Given a scientific paper (PDF) and its own supplementary video, re-measure a published kinematic number
from the pixels and return a verdict - REPRODUCED / NOT REPRODUCED / CANNOT MEASURE - with an
uncertainty interval and a visual receipt. The model proposes; tracking and code measure.

## Architecture (one pipeline, each stage checkable)
1. read    - Muse Spark 1.3 reads PDF + video: claims, fps/playback, scale reference, object phrase (strict JSON schema).
2. scale   - Spark proposes the reference (grid / scale bar) location; OpenCV measures it to sub-pixel; disagreement > 5% is reported.
3. track   - SAM 3.1 video tracks the object from the noun phrase; masks -> centroids; long clips segmented + retried.
4. measure - kinematics in code: ballistic fit, spline velocity, smoothing-sensitivity interval, gravity self-check.
5. verdict - published value inside / outside the measured interval; CANNOT MEASURE when a self-check fails.
6. receipt - overlay video + JSON report with every number and its provenance.

## Stages
- S0 Day-1 spike: DONE 2026-10-27 (beetle jump reproduced; see spike/beetle/RESULT.md on Sam's machine).
- S1 Core engine + CLI end to end on the beetle case, unit tests.            <- current
- S2 Calibration benchmark: synthetic videos with known truth and planted claim errors (1/5/20%): detection power + false alarms.
- S3 Two more real papers (jumping spider Sci Rep 2018; one more), each with its own verdict.
- S4 Web app (upload or pick a case -> live progress -> receipt), cached cases, rate limit, no key in client.
- S5 Demo video (3 min, AI voice + captions), README, submission.

## Decisions
- D1 Spark never supplies a final number; every number comes from tracking + code (Day-1: Spark guessed Apollo timing, grid spacing 7% off).
- D2 Report intervals, not single values (velocity depends on smoothing).
- D3 Only CC BY / CC0 / public-domain inputs; record licence per case.
- D4 Non-clinical papers only (hackathon bans medical advice).

## Risks
- Few real papers have video + visible scale + stated fps -> curated cases + synthetic benchmark.
- SAM on very small objects (Apollo failed) -> state limits, CANNOT MEASURE path.
- Long videos drop the stream (Apollo astronaut run) -> segment + retry.
