"""Generate a short MusicGen clip from today's weather.

The zip code is the same one main.py uses. The forecast picks the mood,
scale, and tempo. A random genre supplies the band, including drums.
"""

from __future__ import annotations

import logging
import os
import random
from datetime import datetime
from pathlib import Path

os.environ["HF_HOME"] = str(Path(__file__).resolve().parent / "model-cache")

import numpy as np
import scipy.io.wavfile
import torch
from transformers import AutoProcessor, MusicgenForConditionalGeneration

from api_connections.open_mateo import OpenMateo
from const.weather_scale_mappings import WEATHER_SCALES, bpm_for_gust

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)
log = logging.getLogger("ai_music_gen")
logging.getLogger("httpx2").setLevel(logging.WARNING)
logging.getLogger("httpcore2").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.ERROR)

# Same default as main.py. Change the string to hear somewhere else.
ZIP_CODE = "11215"
MODEL_NAME = "facebook/musicgen-large"
SECONDS = 25
GUIDANCE_SCALE = 3
# MusicGen was tuned at top-k 250. The library default of 50 collapses into noise.
TOP_K = 250
TEMPERATURE = 1.0
FADE_SECONDS = 4
CLIPS_DIR = Path(__file__).resolve().parent / "weather_clips"

# A suggestion for each weather scale. The names match WEATHER_SCALES.
_SCALE_MOOD = {
    "major": "a bright, open major key",
    "minor": "a somber, introspective minor key",
    "dorian": "Dorian minor color: mellow minor harmony with a gently raised sixth and open, unresolved chords",
    "phrygian": "a tense, dark phrygian mode",
    "lydian": "a dreamy, floating lydian mode",
    "mixolydian": "a warm, bluesy mixolydian mode",
    "locrian": "an unstable, uneasy locrian mode",
    "harmonic_minor": "a dramatic harmonic minor",
    "whole_tone": "a surreal, weightless whole-tone scale",
    "pentatonic_major": "a simple, folk-like major pentatonic",
    "pentatonic_minor": "a sparse, bluesy minor pentatonic",
    "diminished": "an anxious, jagged diminished scale",
}

# Each genre names its own band. MusicGen follows concrete instruments, and drums have to be one of them.
_GENRES = {
    "jazz": "a drum kit, walking upright bass, piano, and horns",
    "soul": "a drum kit, electric bass, electric piano, and guitar",
    "folk": "a drum kit, acoustic bass, acoustic guitar, and fiddle",
    "bossa nova": "brushed drums, bass, nylon-string guitar, and piano",
    "chamber music": "timpani, strings, and woodwinds",
    "afrobeat": "a drum kit, percussion, bass guitar, and horns",
    "reggae": "a drum kit on the offbeat, deep bass guitar, and rhythm guitar",
    "funk": "a tight drum kit, slap bass, rhythm guitar, and horns",
    "blues": "a drum kit, bass, and electric guitar",
    "samba": "a samba drum section, bass, and guitar",
    "gospel": "a drum kit, bass, organ, and piano",
    "indie rock": "a drum kit, bass guitar, and electric guitars",
    "classical": "timpani, orchestral strings, and woodwinds",
    "cumbia": "hand drums and a drum kit, bass, and accordion",
    "highlife": "a drum kit, percussion, bass guitar, and electric guitar",
    "tango": "light percussion, bandoneon, violin, and piano",
    "desert blues": "hand drums, bass, and electric guitar",
    "post-rock": "a drum kit, bass guitar, and electric guitars",
    "waltz": "a drum kit in three, bass, and piano",
    "ska": "a drum kit, walking bass, rhythm guitar, and horns",
}

def music_prompt(weather: dict[str, object]) -> tuple[str, str, float, str]:
    """Turn today's forecast into a MusicGen prompt, plus the scale, tempo, and genre."""
    code = weather["weather_code"]
    if not isinstance(code, int):
        raise TypeError(f"Expected an integer weather code, got {code!r}.")
    try:
        scale_name = WEATHER_SCALES[code]
    except KeyError:
        codes = ", ".join(str(known) for known in sorted(WEATHER_SCALES))
        raise ValueError(f"Unknown weather code {code}. Choose from: {codes}.") from None

    gust = weather["wind_gust"]
    gust_mph = gust if isinstance(gust, (int, float)) else None
    bpm = bpm_for_gust(gust_mph)
    condition = str(weather["condition"])
    place = str(weather["place"])
    genre = random.choice(tuple(_GENRES))
    prompt = (
        f"Instrumental {genre} with {_GENRES[genre]}. "
        f"The drums keep a clear beat, the bass moves, and a melody plays, around {bpm:g} BPM. "
        f"The mood is {_weather_mood(condition)} and {_temperature_character(weather['high'], weather['low'])}, "
        f"like the weather in {place}. "
        f"A good fit is {_SCALE_MOOD[scale_name]}. "
        f"{_wind_motion(gust_mph)} "
        f"No vocals."
    )
    return prompt, scale_name, bpm, genre


def _weather_mood(condition: str) -> str:
    """Name the weather as a mood. Timbre words send MusicGen toward synth noise."""
    text = condition.casefold()
    if "thunder" in text:
        return "stormy"
    if any(word in text for word in ("snow", "sleet", "freezing")):
        return "quiet"
    if any(word in text for word in ("drizzle", "rain", "shower")):
        return "rainy"
    if any(word in text for word in ("fog", "mist")):
        return "hazy"
    if any(word in text for word in ("cloud", "overcast")):
        return "mellow"
    if any(word in text for word in ("clear", "sun")):
        return "bright"
    return "calm"


def _temperature_character(high: object, low: object) -> str:
    values = [value for value in (high, low) if isinstance(value, (int, float))]
    if not values:
        return "mild"
    midpoint = sum(values) / len(values)
    if midpoint < 32:
        return "cold"
    if midpoint < 45:
        return "chilly"
    if midpoint < 60:
        return "mild"
    if midpoint < 75:
        return "warm"
    return "hot"


def _wind_motion(gust_mph: float | None) -> str:
    """Phrase motion from the same gust that sets the tempo."""
    if gust_mph is None or gust_mph < 7:
        return "The beat stays steady."
    if gust_mph < 15:
        return "The groove moves at an easy pace, and the drums keep time."
    if gust_mph < 25:
        return "The phrases sway a little, and the drums keep time."
    if gust_mph < 39:
        return "The dynamics swell, and the drums keep time."
    if gust_mph < 55:
        return "The playing leans and pushes, and the drums stay driving."
    return "The band surges, and the drums stay driving."


def _file_token(text: str) -> str:
    """Turn a label into a Windows-safe filename piece."""
    cleaned = "".join(ch for ch in text.strip() if ch not in '\\/:*?"<>|')
    return cleaned.replace(" ", "_")


def clip_path(weather_name: str, place: str, moment: datetime | None = None) -> Path:
    """Name a clip date_time_location_weathername."""
    when = datetime.now().astimezone() if moment is None else moment
    stamp = when.strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3]
    return CLIPS_DIR / f"{stamp}_{_file_token(place)}_{_file_token(weather_name)}.wav"


def fade_out(samples: np.ndarray, rate: int, seconds: float = FADE_SECONDS) -> np.ndarray:
    """Lower the last stretch of audio to silence."""
    fade_samples = min(len(samples), int(rate * seconds))
    if fade_samples <= 1:
        return samples
    faded = samples.copy()
    faded[-fade_samples:] *= np.linspace(1, 0, fade_samples)
    return faded


def generate(prompt: str, weather_name: str, place: str) -> Path:
    tokens = SECONDS * 50
    log.info("Loading %s in float16 on cuda", MODEL_NAME)
    log.info("The first run downloads the model and may take a while")
    processor = AutoProcessor.from_pretrained(MODEL_NAME)
    model = MusicgenForConditionalGeneration.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float16,
    ).to("cuda")
    log.info("Model is on %s", torch.cuda.get_device_name(0))
    log.info(
        "Generating %s seconds, %s tokens, guidance scale %s, top-k %s, temperature %s",
        SECONDS,
        tokens,
        GUIDANCE_SCALE,
        TOP_K,
        TEMPERATURE,
    )
    inputs = processor(text=[prompt], padding=True, return_tensors="pt").to("cuda")
    with torch.inference_mode():
        audio = model.generate(
            **inputs,
            do_sample=True,
            guidance_scale=GUIDANCE_SCALE,
            max_new_tokens=tokens,
            top_k=TOP_K,
            temperature=TEMPERATURE,
        )
    samples = audio[0, 0].float().cpu().numpy()
    samples = np.clip(samples, -1, 1)
    rate = model.config.audio_encoder.sampling_rate
    samples = fade_out(samples, rate)
    log.info("Fading out over %s seconds", FADE_SECONDS)
    destination = clip_path(weather_name, place)
    destination.parent.mkdir(parents=True, exist_ok=True)
    log.info("Writing %s at %s Hz", destination, rate)
    scipy.io.wavfile.write(
        destination,
        rate,
        (samples * 32767).astype(np.int16),
    )
    log.info("Saved %s", destination)
    return destination


if __name__ == "__main__":
    log.info("Zip code %s", ZIP_CODE)
    log.info("Asking Open-Meteo for today's forecast")
    weather = OpenMateo(ZIP_CODE).today()
    log.info("Place: %s", weather["place"])
    log.info("Condition: %s (code %s)", weather["condition"], weather["weather_code"])
    log.info("High: %s F", weather["high"])
    log.info("Low: %s F", weather["low"])
    log.info("Wind gust: %s mph", weather["wind_gust"])
    prompt, scale_name, bpm, genre = music_prompt(weather)
    log.info("Genre: %s", genre)
    log.info("Scale: %s", scale_name)
    log.info("Tempo: %g bpm", bpm)
    log.info("Prompt: %s", prompt)
    condition = weather["condition"]
    place = weather["place"]
    if not isinstance(condition, str):
        raise TypeError(f"Expected a weather name, got {condition!r}.")
    if not isinstance(place, str):
        raise TypeError(f"Expected a place name, got {place!r}.")
    generate(prompt, condition, place)
    log.info(
        "Clip is %s %s in %s, %s at %g bpm",
        genre,
        condition,
        weather["place"],
        scale_name,
        bpm,
    )
    log.info("Prompt was: %s", prompt)
