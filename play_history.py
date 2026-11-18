"""Play saved jingles and MusicGen clips.

python play_history.py
    Play the newest file.

python play_history.py --all
    Play every saved file, oldest first.

python play_history.py history/2026-10-30T13-03-00-123_Fog_minor.json
    Play one file. A bare filename is looked up in history/ and weather_clips/.

Older jingles are JSON and are rebuilt. Newer jingles and AI clips are wav files.
"""

from __future__ import annotations

import sys
import winsound
from pathlib import Path

from classes.jingle import HISTORY_DIR, Jingle

CLIPS_DIR = HISTORY_DIR.parent / "weather_clips"


def _saved_files() -> list[Path]:
    found: list[Path] = []
    if HISTORY_DIR.is_dir():
        found.extend(
            path
            for path in HISTORY_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in {".json", ".wav"}
        )
    if CLIPS_DIR.is_dir():
        found.extend(path for path in CLIPS_DIR.glob("*.wav") if path.is_file())
    return sorted(found, key=lambda path: path.name)


def _resolve(name: str) -> Path:
    path = Path(name)
    if path.is_file():
        return path
    for folder in (HISTORY_DIR, CLIPS_DIR):
        candidate = folder / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"No saved clip at {name}.")


def _play_wav(path: Path) -> None:
    if sys.platform != "win32":
        raise RuntimeError(f"Playing {path.name} needs Windows.")
    winsound.PlaySound(str(path), winsound.SND_FILENAME)


def _play(path: Path) -> None:
    if path.suffix.lower() == ".json":
        Jingle.play_file(path)
        return
    if path.suffix.lower() == ".wav":
        _play_wav(path)
        return
    raise ValueError(f"Cannot play {path.name}. Expected a .json jingle or a .wav clip.")


def main() -> None:
    args = sys.argv[1:]
    files = _saved_files()
    if not args:
        if not files:
            print(f"No saved clips in {HISTORY_DIR} or {CLIPS_DIR}.")
            return
        chosen = [files[-1]]
    elif args == ["--all"]:
        if not files:
            print(f"No saved clips in {HISTORY_DIR} or {CLIPS_DIR}.")
            return
        chosen = files
    else:
        chosen = [_resolve(args[0])]

    for path in chosen:
        print(path.name)
        _play(path)


if __name__ == "__main__":
    main()
