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
    "frame size {w}x{h}. Report the overlay text exactly, any capture/playback frame rates printed, the kind of "
    "spatial reference visible, your estimate of one grid square in pixels if there is a grid, a band of rows "
    "where grid lines are clearly visible and not covered by the object, floor or text, and the moving object's "
    "box [x1, y1, x2, y2]. Do not invent values you cannot see; use null.")


def _structured(content: list[dict], name: str, schema: dict) -> tuple[dict, dict]:
    r = meta.client().responses.create(
        model=meta.SPARK, max_output_tokens=24000, input=[{"role": "user", "content": content}],
        text={"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}})
    usage = r.usage.model_dump() if r.usage else {}
    return json.loads(r.output_text), usage


def read_paper(pdf: Path) -> tuple[dict, dict]:
    fid = meta.upload(pdf, "application/pdf")
    return _structured([{"type": "input_file", "file_id": fid}, {"type": "input_text", "text": PAPER_PROMPT}],
                       "paper_reading", PAPER_SCHEMA)


def read_frame(png: Path, width: int, height: int) -> tuple[dict, dict]:
    url = "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode()
    return _structured([{"type": "input_image", "image_url": url},
                        {"type": "input_text", "text": FRAME_PROMPT.format(w=width, h=height)}],
                       "frame_reading", FRAME_SCHEMA)
