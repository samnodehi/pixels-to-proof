# Fault injection

Each row corrupts one model proposal of a real audit (beetle, base run beetle-20261030-32dbbf4) the way a wrong model answer would, then re-runs the agent. Re-proposals in these runs are live model calls, so a repeat run can differ.

- **caught**: a check fired and the affected result became a refusal or NOT CHECKED
- **recovered**: a check fired (or Muse Spark re-proposed) and the final results equal the uncorrupted run
- **no effect**: nothing fired and nothing changed (code overrode the field, or it was not needed)
- **WRONG**: a verdict changed to a different non-refusal — must not happen

| mutation | outcome | what happened | gate rejections that fired |
|---|---|---|---|
| column map: trajectory angle swapped with a body-posture angle | no effect | nothing fired and nothing changed | — |
| column unit: distances in mm instead of m | caught | claim ('jump_distance', 'max', 0.02375, None): MATCHES TABLE -> NOT CHECKED | G1 plan []: v1 column DistanceRawm range: 2.33e-06..2.375e-05 in SI outside plausible range; dropped; G1 plan []: v1 column DistanceTrajm range: 2.893e-06..2.494e-05 in SI outside plausible range; dro |
| column unit: speed in mm/s instead of m/s | caught | journal.pone.0256509.s004_s2: REPRODUCED -> CANNOT MEASURE | G1 plan []: v1 column velocity.max range: 0.0001373..0.0008673 in SI outside plausible range; dropped; G4 comparison [6509.s003_s1]: no single, absolute take-off speed column in an event table: nothin |
| uncertainty: relative error claimed absolute, unsupported quote | recovered | a check fired and the final results equal the unmutated run | G1 plan []: v1 column VelError kind: 'absolute' not supported by a verbatim quote about it; set to unknown; G1 plan []: v2 claim '0.12 mm3': quote not found verbatim or value not in quote; dropped |
| scale: grid square 10 mm instead of 5 mm | caught | journal.pone.0256509.s004_s2: REPRODUCED -> CANNOT MEASURE; claim ('other_duration', 'mean', 0.0069, 0.0143): None -> REFUSED | G1 plan []: v1 scale size: 10.0 mm: no verbatim quote stating that size; dropped; route []: REFUSED: When pooled, the combined latch-decoupling and launch phases lasted 6.; G4 scale [6509.s004_s1]: th |
| frame rate: paper rate 1,000 fps instead of 3,200 | caught | claim ('other', 'single_event', 30.0, None): None -> REFUSED; claim ('other', 'single_event', 3200.0, None): None -> REFUSED; claim ('other', 'single_event', 60 | G1 plan []: v1 video journal.pone.0256509.s004.mp4 fps: fps 1000: no verbatim quote stating that number; dropped |
| claim: misread value 0.57 instead of 0.47 | caught | claim ('other_duration', 'mean', 0.0069, 0.0143): None -> REFUSED; claim ('other', 'single_event', 0.12, None): None -> REFUSED; claim ('other', 'mean', 110.0,  | G1 plan []: v1 claim 'Larvae reached takeoff velocities of 0.47 ± 0.15 m': quote not found verbatim or value not in quote;; route []: REFUSED: When pooled, the combined latch-decoupling and launch pha |
| claim: mean labelled a single event | recovered | a check fired and the final results equal the unmutated run | route []: proposed as a single event, but it equals the mean of 'velocity.max': routed to the table check |
| frame read: rate 1,000 fps (not printed) | recovered | a check fired and the final results equal the unmutated run | G4 frame rate [6509.s004_s2]: Spark read 1000 fps but that number is not printed on the shot |
| frame read: rate 1,000 fps, overlay misread to match | caught | journal.pone.0256509.s004_s2: REPRODUCED -> CANNOT MEASURE | G5 gravity [6509.s004_s2]: 0.98 m/s^2 from the flight (-90.0% vs 9.81); G3 blind pairing [6509.s004_s2]: best row c_21382_421_croppedxypts is only 1.01x closer than c_21382_487_croppedxypts (needs 2.0 |
| frame read: object box on the background | recovered | a check fired and the final results equal the unmutated run | G5 track [6509.s004_s2]: box from Muse Spark: tracked mask barely moves (likely background, not the object); G5 track [6509.s004_s2]: text 'beetle larva': track begins with the object already moving ( |
| frame read: grid not seen | no effect | nothing fired and nothing changed | — |

caught 6, recovered 4, no effect 2, wrong verdicts 0, errors 0 (of 12)
