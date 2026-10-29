# Demo narration

Run in this folder, in order:

1. `python3 make_sections.py` — spoken text of `../SCRIPT_DRAFT.md`, one entry per section → `sections.json`.
2. `P2P_ENV_FILE=<path to env file with OPENROUTER_API_KEY> python3 tts.py 0 1 2 3 4 5 6 7` — one MP3 per section,
   ElevenLabs `eleven-v4`, voice `daniel`, via OpenRouter `/api/v1/audio/speech`.
3. `python3 asr.py` — faster-whisper `small.en` word timestamps → `words.json` (used only for caption timing; caption
   text is the script's own).
4. `python3 assemble.py` — `narration.mp3` (0.5 s lead, 0.7 s between sections, loudness −16 LUFS) and
   `narration.srt` (one short line per cue, aligned to the words in step 3).

Recorded 2026-10-29: narration 2:52 (172.4 s). The MP3s are not committed; they are kept in Sam's hackathon folder.
Pronunciation check: whisper hears "Muse Spark" as "New Spark" unless told the name in its prompt, so the names are
checked by ear.
