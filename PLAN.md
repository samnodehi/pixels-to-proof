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
4. measure - kinematics in code: skipped-frame repair (periodic double steps), ballistic fit, spline velocity, bootstrap interval, two self-checks (gravity; no sideways acceleration).
5. verdict - published value inside / outside the measured interval; CANNOT MEASURE when a self-check fails.
6. receipt - overlay video + JSON report with every number and its provenance.

## Stages
- S0 Day-1 spike: DONE 2026-10-27 (beetle jump reproduced; see spike/beetle/RESULT.md on Sam's machine).
- S1 Core engine + CLI end to end on the beetle case, unit tests: DONE 2026-10-27.
- S2 Calibration benchmark: DONE 2026-10-27 (48 synthetic cases, seed 2026, bench/RESULTS_seed2026.md): median error 0.05%, 0/12 false alarms, 23/24 planted errors >=5% flagged (1 CANNOT MEASURE), 6/8 at 1%, 4/4 wrong frame rates caught by the gravity check. Caveat: synthetic = clean ball on grid; real footage is harder.
- S3 Second real paper: DONE 2026-10-27 (jumping spider, Sci Rep 2018, CC BY 4.0): CANNOT MEASURE, with reasons (see Findings). A third paper is optional.
- S4 Web app (upload or pick a case -> live progress -> receipt), cached cases, rate limit, no key in client.
- S5 Demo video (3 min, AI voice + captions), README, submission.

## Findings so far
- Beetle (PLOS ONE e0256509, jump 488): ballistic take-off speed 0.436 m/s (interval 0.425-0.447, gravity check 10.02 m/s^2) vs published 0.405 +/- 0.024 (authors' spline method). Overlap is marginal: REPRODUCED. On synthetic flights the spline-peak method reads 3-10% low for slow steep jumps, which is the likely cause of the gap (INFERENCE).

- Spider (Sci Rep 8:7142, Supplementary Movie S2, 'Level jumps' montage, 3 panels, gaps 30/45/60 mm): all three CANNOT MEASURE. At the stated 3,200 fps and the platform-gap scale, gravity from the flight is +42/+27/+39% and sideways deceleration is 46/69/31% of the vertical acceleration (free flight: ~0; beetle 0.7%). The montage skips one frame every 13-14 frames (7/12/17 found, regular period, FACT from the track), repaired before fitting; the checks still fail. Cause not separable from the video (silk safety line, depth motion, other time-base editing: INFERENCE candidates). Published values 0.571/0.838/0.952 m/s; the untrusted raw fits give 0.88/1.09/1.21. Descending jumps (4 panels) are not cased: flight_window requires the object to rise above its start.

## Decisions
- D1 Spark never supplies a final number; every number comes from tracking + code (Day-1: Spark guessed Apollo timing, grid spacing 7% off).
- D2 Report intervals, not single values (velocity depends on smoothing).
- D3 Only CC BY / CC0 / public-domain inputs; record licence per case.
- D4 Non-clinical papers only (hackathon bans medical advice).
- D5 Primary speed estimate = ballistic fit of the flight (validated by the gravity check); the spline method papers use is reported alongside, not used for the verdict.
- D7 Free-flight self-check: |horizontal acceleration| / |vertical acceleration| must stay below 10%. The ratio does not depend on scale or frame rate, so it tests the motion model itself (drag, tether, depth motion, camera roll). Synthetic max 0.7%, beetle 0.7%.
- D8 Skipped frames are repaired only when the long steps are periodic (>= 3 events on one regular period): edits drop frames regularly, pixel quantisation does not. Bench re-run with the repair: results identical to the committed RESULTS_seed2026.md (no false repairs on 47 synthetic tracks or the beetle).
- D6 Muse Spark's box on frame 0 is the first SAM prompt; text prompt is the fallback; tracks failing a quality check (mask area jump, no motion) are rejected; no usable track -> CANNOT MEASURE.

## Risks
- Few real papers have video + visible scale + stated fps -> curated cases + synthetic benchmark.
- SAM on very small objects (Apollo failed) -> state limits, CANNOT MEASURE path.
- Long videos drop the stream (Apollo astronaut run) -> segment + retry.
