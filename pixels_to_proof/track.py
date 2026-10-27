"""SAM 3.1 video tracking -> per-frame centroids.

The streaming adapter follows Meta's cookbook example `07_sam/01_api_basics/python/sam_api.py`
(MIT licence, Copyright Meta Platforms, Inc.); see NOTICE.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import aclosing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from meta_sam_parser import (
    ResponsesEventLike,
    VideoSegmentationResult,
    decode_mask_to_raster,
    parse_responses_stream,
    video_segmentation_format,
)

from . import meta


@dataclass
class Point:
    frame: int        # frame index in the analysed clip
    cx: float         # mask centroid, pixels
    cy: float
    area: int         # mask area, pixels
    left: int         # mask bounds
    top: int
    right: int
    bottom: int


async def _events(stream: AsyncIterable[Any]) -> AsyncIterator[ResponsesEventLike]:
    # The API sends response.content_part.done but not response.output_text.done,
    # which the parser needs to close a lane; synthesise it (as in Meta's cookbook).
    done: set[tuple[object, object, object]] = set()
    async for event in stream:
        data = event.model_dump() if hasattr(event, "model_dump") else dict(event)
        lane = (data.get("item_id"), data.get("output_index"), data.get("content_index"))
        if data.get("type") == "response.output_text.done":
            if lane not in done:
                done.add(lane)
                yield data
            continue
        yield data
        part = data.get("part")
        if (data.get("type") == "response.content_part.done" and lane not in done
                and isinstance(part, dict) and part.get("type") == "output_text"
                and isinstance(part.get("text"), str)):
            done.add(lane)
            yield {"type": "response.output_text.done", "item_id": data.get("item_id"),
                   "output_index": data.get("output_index"), "content_index": data.get("content_index"),
                   "text": part["text"]}


async def _segment(file_id: str, concept: str) -> VideoSegmentationResult:
    async with meta.async_client() as api:
        stream = await api.responses.create(
            model=meta.SAM, stream=True,
            input=[{"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": concept.strip()},
                {"type": "input_video", "file_id": file_id}]}])
        async with stream, aclosing(_events(stream)) as events:
            parsed = parse_responses_stream(events, video_segmentation_format())
            async with parsed:
                async for _ in parsed:
                    pass
                return await parsed.final_result()


def segment(file_id: str, concept: str, attempts: int = 3) -> VideoSegmentationResult:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            result = asyncio.run(_segment(file_id, concept))
            if result.outcome.status != "completed":
                raise RuntimeError(f"SAM outcome {result.outcome.status}: {getattr(result.outcome, 'reason', '')}")
            return result
        except Exception as exc:  # network drops were observed on long clips
            last = exc
    raise RuntimeError(f"SAM failed after {attempts} attempts: {last}") from last


def tracks(result: VideoSegmentationResult) -> dict[str, list[Point]]:
    """Centroid of every mask, grouped by SAM object id, ordered by frame."""
    out: dict[str, list[Point]] = {}
    for rec in result.records:
        if rec.kind != "mask" or rec.frame is None:
            continue
        w, h = rec.mask.width, rec.mask.height
        raster = np.frombuffer(decode_mask_to_raster(rec.mask), dtype=np.uint8).reshape(h, w)
        ys, xs = np.nonzero(raster)
        if len(xs) == 0:
            continue
        b = rec.bounds
        out.setdefault(rec.object_id, []).append(Point(
            frame=rec.frame.frame_index, cx=float(b.left + xs.mean()), cy=float(b.top + ys.mean()),
            area=int(len(xs)), left=int(b.left), top=int(b.top), right=int(b.right), bottom=int(b.bottom)))
    for pts in out.values():
        pts.sort(key=lambda p: p.frame)
    return out


def main_track(result: VideoSegmentationResult) -> tuple[str, list[Point]]:
    """The longest track is taken as the measured object; the caller reports the others."""
    all_tracks = tracks(result)
    if not all_tracks:
        raise LookupError("SAM returned no masks for this concept.")
    oid = max(all_tracks, key=lambda k: len(all_tracks[k]))
    return oid, all_tracks[oid]


def cut_clip(src: Path, dst: Path, start_s: float, end_s: float) -> Path:
    """Frame-accurate re-encode of [start, end) so frame indices start at 0."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start_s:.3f}", "-to", f"{end_s:.3f}", "-i", str(src),
                    "-an", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", str(dst)], check=True)
    return dst


def save_track(points: list[Point], path: Path) -> None:
    path.write_text(json.dumps([asdict(p) for p in points]))


def load_track(path: Path) -> list[Point]:
    return [Point(**p) for p in json.loads(path.read_text())]
