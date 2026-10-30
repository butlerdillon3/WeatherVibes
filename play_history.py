"""Play jingles saved in history/.

python play_history.py
    Play the newest file.

python play_history.py --all
    Play every saved jingle, oldest first.

python play_history.py history/2026-10-30T13-03-00-123_Fog_minor.json
    Play one file. A bare filename is looked up in history/.
"""

from __future__ import annotations

import sys
from pathlib import Path

from classes.jingle import HISTORY_DIR, Jingle


def _saved_files() -> list[Path]:
    if not HISTORY_DIR.is_dir():
        return []
    return sorted(path for path in HISTORY_DIR.glob("*.json") if path.is_file())


def _resolve(name: str) -> Path:
    path = Path(name)
    if path.is_file():
        return path
    candidate = HISTORY_DIR / name
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"No saved jingle at {name}.")


def main() -> None:
    args = sys.argv[1:]
    files = _saved_files()
    if not args:
        if not files:
            print(f"No saved jingles in {HISTORY_DIR}.")
            return
        chosen = [files[-1]]
    elif args == ["--all"]:
        if not files:
            print(f"No saved jingles in {HISTORY_DIR}.")
            return
        chosen = files
    else:
        chosen = [_resolve(args[0])]

    for path in chosen:
        print(path.name)
        Jingle.play_file(path)


if __name__ == "__main__":
    main()
