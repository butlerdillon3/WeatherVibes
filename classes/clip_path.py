"""Filenames shared by the chiptune jingle and the MusicGen clip."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def file_token(text: str) -> str:
    """Turn a label into a Windows-safe filename piece."""
    cleaned = "".join(ch for ch in text.strip() if ch not in '\\/:*?"<>|')
    return cleaned.replace(" ", "_")


def clip_path(
    directory: Path,
    weather_name: str,
    place: str,
    moment: datetime | None = None,
) -> Path:
    """Name a clip date_time_location_weathername.wav."""
    when = datetime.now().astimezone() if moment is None else moment
    stamp = when.strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3]
    return directory / f"{stamp}_{file_token(place)}_{file_token(weather_name)}.wav"
