# Demo video

Built on the narration in `../voice/` (`narration.mp3`, `narration.srt`, `words.json`).

1. Run the app locally (`GRADIO_SERVER_PORT=7861 python3 app.py`), then `python3 locate.py` and `python3 locate2.py`:
   full-page screenshots of the recorded runs (device scale 2) into `shots/`, and the boxes of the rows, cards and
   text that the video highlights into `boxes.json` / `boxes2.json` (CSS px).
2. `python3 assets.py` — the two quoted paper sentences (PDF crops, with the boxes of the highlighted words), raw
   frames, and the data-table snippet, into `assets/`.
3. `python3 render.py [start end out.mp4]` — renders the shot list in `timeline.py` (1920×1080, 30 fps) and burns in
   the captions; `python3 peek.py out.png t1 t2 …` shows single frames for checking.

The shot times in `timeline.py` follow the word timings of the narration; if the narration is regenerated, re-check
them. Rendered 2026-10-29: `demo_v2.mp4`, 2:52 (v1 + "built during the hackathon" on the title cards); not committed.
