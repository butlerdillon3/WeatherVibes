"""Play today's weather as a MusicGen clip or as the chiptune jingle."""

from __future__ import annotations

from api_connections.open_mateo import OpenMateo
from classes.ai_music_gen import AiMusicGen
from classes.jingle import Jingle

# "ai" uses MusicGen. "programatic" uses the chiptune jingle.
GENERATOR = "ai"
ZIP_CODE = "11215"


if __name__ == "__main__":
    weather = OpenMateo(ZIP_CODE).today()
    print(weather)
    if GENERATOR == "ai":
        AiMusicGen(weather).generate()
    elif GENERATOR == "programatic":
        jingle = Jingle(weather)
        tune = jingle.build()
        saved = jingle.save()
        print(f"{jingle.scale_name} at {jingle.synth.bpm:g} bpm")
        print(f"lead:   {jingle.lead_line}")
        print(f"rhythm: {jingle.rhythm_line}")
        print(f"bass:   {jingle.bass_line}")
        print(saved)
        jingle.synth.play(tune)
    else:
        raise ValueError(f"GENERATOR must be 'ai' or 'programatic', got {GENERATOR!r}.")
