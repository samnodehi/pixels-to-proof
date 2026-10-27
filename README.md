# Pixels to Proof

Re-measure a number a scientific paper published, from the paper's own supplementary video.

Muse Spark 1.3 reads the paper and the video and proposes what to measure (the claim, the object, the frame
rate, the scale reference). SAM 3.1 tracks the object in every frame. Code measures: scale from the grid,
ballistic fit, a gravity self-check, a bootstrap interval. The result is a verdict - REPRODUCED,
NOT REPRODUCED or CANNOT MEASURE - with a visual receipt.

Status: under construction during the Meta Global AI Developer Hackathon (Oct 27 - Nov 4, 2026). See PLAN.md.

## Run a case
    pip install -r requirements.txt
    export MODEL_API_KEY=...            # or P2P_SECRETS=/path/to/file with MODEL_API_KEY=...
    python -m pixels_to_proof cases/beetle_pone0256509/case.json --out runs/beetle

Media for each case are downloaded from the publisher (see the case.json for source and licence).
