"""Muse Spark 1.3 reads the paper and the video. It proposes; it never supplies a final number."""
from __future__ import annotations

import base64
import json
from pathlib import Path

from . import meta

_CLAIM = {"type": "object", "additionalProperties": False,
          "properties": {"quantity": {"type": "string"}, "value": {"type": "number"},
                         "plus_minus": {"type": ["number", "null"]}, "unit": {"type": "string"},
                         "quote": {"type": "string"}, "location": {"type": "string"},
                         "measured_from_video": {"type": "boolean"}},
          "required": ["quantity", "value", "plus_minus", "unit", "quote", "location", "measured_from_video"]}

PAPER_SCHEMA = {"type": "object", "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "licence": {"type": "string"},
                    "claims": {"type": "array", "items": _CLAIM},
                    "videos": {"type": "array", "items": {
                        "type": "object", "additionalProperties": False,
                        "properties": {"label": {"type": "string"}, "capture_fps": {"type": ["number", "null"]},
                                       "playback_fps": {"type": ["number", "null"]}, "description": {"type": "string"}},
                        "required": ["label", "capture_fps", "playback_fps", "description"]}},
                    "scale_reference": {"type": "string"},
                    "scale_reference_mm": {"type": ["number", "null"]},
                    "object_noun_phrase": {"type": "string"}},
                "required": ["title", "licence", "claims", "videos", "scale_reference", "scale_reference_mm",
                             "object_noun_phrase"]}

FRAME_SCHEMA = {"type": "object", "additionalProperties": False,
                "properties": {
                    "overlay_text": {"type": "string"},
                    "capture_fps": {"type": ["number", "null"]},
                    "playback_fps": {"type": ["number", "null"]},
                    "reference_kind": {"type": "string", "enum": ["grid", "scale_bar", "ruler", "none"]},
                    "grid_square_px_estimate": {"type": ["number", "null"]},
                    "grid_band_rows": {"type": "array", "items": {"type": "integer"},
                                       "description": "[top, bottom] rows where the grid is clear of the object, floor and text"},
                    "object_box": {"type": "array", "items": {"type": "integer"}},
                    "notes": {"type": "string"}},
                "required": ["overlay_text", "capture_fps", "playback_fps", "reference_kind",
                             "grid_square_px_estimate", "grid_band_rows", "object_box", "notes"]}

PAPER_PROMPT = (
    "Read this scientific paper. Return: its title and licence; every quantitative kinematic claim "
    "(speeds, distances, heights, durations, angles, accelerations) with the exact quote, where it appears, "
    "its value, its +/- if given, and whether it was measured from video; each supplementary video with "
    "capture and playback frame rates if stated; how spatial scale was set and its real size in mm if stated; "
    "and a short noun phrase (1-3 words) that names the moving object for a segmentation model.")

FRAME_PROMPT = (
    "This is one frame of a scientific supplementary video. Pixel coordinates: origin top-left, "
    "frame size {w}x{h}. Report the overlay text exactly, including small print in the corners (frame rate, playback speed, scale notes), any capture/playback frame rates printed, the kind of "
    "spatial reference visible, your estimate of one grid square in pixels if there is a grid, a band of rows "
    "where grid lines are clearly visible and not covered by the object, floor or text, and the moving object's "
    "box [x1, y1, x2, y2]. Do not invent values you cannot see; use null.")


def _structured(content: list[dict], name: str, schema: dict, attempts: int = 3) -> tuple[dict, dict]:
    """Strict-schema call. An answer that is not valid JSON (seen once: truncated output) is retried."""
    last = None
    for _ in range(attempts):
        r = meta.client().responses.create(
            model=meta.SPARK, max_output_tokens=32000, input=[{"role": "user", "content": content}],
            text={"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}})
        usage = r.usage.model_dump() if r.usage else {}
        try:
            return json.loads(r.output_text), usage
        except json.JSONDecodeError as exc:
            last = exc
    raise RuntimeError(f"Muse Spark returned invalid JSON {attempts} times for '{name}': {last}")


def read_paper(pdf: Path) -> tuple[dict, dict]:
    fid = meta.upload(pdf, "application/pdf")
    return _structured([{"type": "input_file", "file_id": fid}, {"type": "input_text", "text": PAPER_PROMPT}],
                       "paper_reading", PAPER_SCHEMA)


TEXT_FRAME_NOTE = (
    " A second image is attached: a later frame of the same recording, where overlay text that is typed in or faded "
    "in after the first frame is complete. Report the overlay text of the recording from both images (each line "
    "once); report the object box and the grid band for the FIRST image only.")


def _png_url(png: Path) -> str:
    mime = "image/jpeg" if png.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return f"data:{mime};base64," + base64.b64encode(png.read_bytes()).decode()


def read_frame(png: Path, width: int, height: int, text_png: Path | None = None) -> tuple[dict, dict]:
    content = [{"type": "input_image", "image_url": _png_url(png)}]
    prompt = FRAME_PROMPT.format(w=width, h=height)
    if text_png is not None:
        content.append({"type": "input_image", "image_url": _png_url(text_png)})
        prompt += TEXT_FRAME_NOTE
    return _structured(content + [{"type": "input_text", "text": prompt}], "frame_reading", FRAME_SCHEMA)


SPLIT_SCHEMA = {"type": "object", "additionalProperties": False,
                "properties": {"shots": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "properties": {
                        "sheet": {"type": "integer", "description": "1-based number of the contact sheet"},
                        "recordings": {"type": "array", "items": {
                            "type": "object", "additionalProperties": False,
                            "properties": {"first_frame": {"type": "integer"}, "last_frame": {"type": "integer"},
                                           "what": {"type": "string"}},
                            "required": ["first_frame", "last_frame", "what"]}},
                        "evidence": {"type": "string",
                                     "description": "what in the tiles shows where one recording ends and the next begins"}},
                    "required": ["sheet", "recordings", "evidence"]}}},
                "required": ["shots"]}

SPLIT_PROMPT = (
    "Each attached image is a contact sheet of one shot of a scientific supplementary video ({video}). Every tile is "
    "labelled with its frame number (top-left, yellow); tiles are evenly spaced, left to right, top to bottom. A shot "
    "found by cut detection can still contain several separate recordings joined by a dissolve, a wipe or a change of "
    "title (for example one jump by a male, then one by a female). For each sheet, list the separate recordings with "
    "the frame numbers of their first and last tiles, leaving out transition tiles (two scenes blended) and title "
    "cards. If the sheet is one continuous recording, return exactly one recording spanning it. Say what shows the "
    "boundaries. Sheets: {sheets}.")


def split_shots(sheets: list[Path], video: str, ranges: list[tuple[int, int]]) -> tuple[dict, dict]:
    desc = "; ".join(f"sheet {i + 1} = frames {a}-{b}" for i, (a, b) in enumerate(ranges))
    content = [{"type": "input_image", "image_url": _png_url(p)} for p in sheets]
    content.append({"type": "input_text", "text": SPLIT_PROMPT.format(video=video, sheets=desc)})
    return _structured(content, "shot_split", SPLIT_SCHEMA)


BOX_SCHEMA = {"type": "object", "additionalProperties": False,
              "properties": {"object_box": {"type": "array", "items": {"type": "integer"}},
                             "what_is_in_the_box": {"type": "string"},
                             "why_the_previous_failed": {"type": "string"}},
              "required": ["object_box", "what_is_in_the_box", "why_the_previous_failed"]}

REBOX_PROMPT = (
    "This is frame 0 of a scientific high-speed video ({w}x{h} px, origin top-left). A tracker was started on the "
    "moving animal '{phrase}' and its result was rejected by an automatic check: {reason}. Previous box(es): {boxes}. "
    "Look again and give a tight box [x1, y1, x2, y2] around the animal that later jumps, not around the background, "
    "a shadow, a label or the substrate. Say what is in your box and why the previous attempt likely failed.")


def repropose_box(png: Path, width: int, height: int, phrase: str, reason: str, boxes: list) -> tuple[dict, dict]:
    return _structured([{"type": "input_image", "image_url": _png_url(png)},
                        {"type": "input_text", "text": REBOX_PROMPT.format(w=width, h=height, phrase=phrase,
                                                                            reason=reason, boxes=boxes)}],
                       "rebox", BOX_SCHEMA)
