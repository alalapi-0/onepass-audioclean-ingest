"""Media classification and audio stream selection helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from .meta import MetaError


@dataclass
class AudioStreamInfo:
    index: int
    codec_name: Optional[str]
    sample_rate: Optional[int]
    channels: Optional[int]
    channel_layout: Optional[str]
    bit_rate: Optional[int]
    language: Optional[str]
    disposition: Optional[Dict[str, Any]] = None


@dataclass
class VideoStreamInfo:
    index: int
    codec_name: Optional[str]
    width: Optional[int]
    height: Optional[int]
    r_frame_rate: Optional[str]


def classify_input(path: Path, ffprobe_data: Optional[Dict[str, Any]]) -> Literal["audio", "video", "unknown"]:
    """Classify input using stream information when possible."""

    if ffprobe_data is None:
        return "unknown"

    streams = ffprobe_data.get("audio_streams", []) or []
    video_streams = ffprobe_data.get("video_streams", []) or []

    if video_streams and streams:
        return "video"
    if streams:
        return "audio"

    ext = path.suffix.lower()
    if ext in {".mp4", ".mkv", ".mov", ".avi", ".flv"}:
        return "video"
    if ext in {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus"}:
        return "audio"
    return "unknown"


def _quality_score(stream: Dict[str, Any]) -> Tuple[int, int, int]:
    channels = stream.get("channels") or 0
    sample_rate = stream.get("sample_rate") or 0
    bit_rate = stream.get("bit_rate") or 0
    return channels, sample_rate, bit_rate


def _find_stream_by_index(audio_streams: List[Dict[str, Any]], index: int) -> Optional[Dict[str, Any]]:
    for stream in audio_streams:
        if stream.get("index") == index:
            return stream
    return None


def select_audio_stream(
    ffprobe_summary: Optional[Dict[str, Any]],
    preferred_index: Optional[int] = None,
    preferred_language: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], List[MetaError], List[Dict[str, Any]]]:
    """Select an audio stream using a deterministic strategy."""

    errors: List[MetaError] = []
    warnings: List[Dict[str, Any]] = []

    if ffprobe_summary is None:
        warnings.append({"code": "probe_missing", "message": "No ffprobe summary available", "detail": None})
        return None, errors, warnings

    audio_streams = ffprobe_summary.get("audio_streams") or []
    if not audio_streams:
        errors.append(
            MetaError(
                code="no_audio_stream",
                message="No audio stream available for extraction",
                hint="Provide media with at least one audio stream.",
            )
        )
        return None, errors, warnings

    if preferred_index is not None:
        selected = _find_stream_by_index(audio_streams, preferred_index)
        if selected is None:
            errors.append(
                MetaError(
                    code="invalid_audio_stream_index",
                    message=f"Audio stream index {preferred_index} not found",
                    hint="Use ffprobe to list available streams and choose a valid index.",
                )
            )
            return None, errors, warnings
        return selected, errors, warnings

    language_normalized = preferred_language.lower() if preferred_language else None
    candidates = audio_streams
    if language_normalized:
        language_matches = [
            stream for stream in audio_streams if (stream.get("language") or "").lower() == language_normalized
        ]
        if language_matches:
            candidates = language_matches
        else:
            errors.append(
                MetaError(
                    code="audio_language_not_found",
                    message=f"Requested audio language '{preferred_language}' not found",
                    hint="Choose a language tag present in the input or omit --audio-language.",
                )
            )
            return None, errors, warnings

    scored = list(enumerate(candidates))
    scored.sort(key=lambda item: (_quality_score(item[1])), reverse=True)
    selected = scored[0][1] if scored else None
    return selected, errors, warnings
