# WeatherVibes

WeatherVibes turns today's weather into a short 8-bit jingle.

A US zip code is looked up on [Open-Meteo](https://open-meteo.com/). The day's weather code picks a musical scale, and the day's maximum wind gust can speed the tempo up. The lead sings one small shape three times, the chords under it change, and the last bar falls to the tonic and holds it. Each run is a new tune in that weather's scale.

`main.py` is set to zip code `11215`. Change that string to hear somewhere else.

## Run

Python 3.14 or newer, with [Poetry](https://python-poetry.org/).

```bash
poetry install
poetry run python main.py
```

The script prints the forecast, the scale, the tempo, and the lead, rhythm, and bass lines, then plays the jingle through your speakers.

## Play a saved jingle

Every run is written to `history/` as JSON. The file name is the time, the weather name, and the scale, for example `2026-10-30T14-04-30-230_Clear_sky_major.json`. Those files stay on your machine and are not committed.

```bash
poetry run python play_history.py
poetry run python play_history.py --all
poetry run python play_history.py history/2026-10-30T14-04-30-230_Clear_sky_major.json
```

With no arguments, the newest file plays. `--all` plays every saved jingle, oldest first. A bare file name is looked up in `history/`.

## How weather becomes music

The maps live in `const/weather_scale_mappings.py`.

The weather code chooses the scale. Clear sky is major. Fog is minor. Freezing rain leans phrygian or locrian. A thunderstorm with heavy hail is whole tone. The same jingle shape is used every time, so the scale is what makes the day sound like itself.

The tempo starts at 120 bpm. Gusts under 25 mph leave it there. A strong breeze adds 10 bpm, a gale adds 30, and a hurricane adds 70. The gust is the day's maximum, in miles per hour.

## Layout

- `main.py` fetches the forecast, builds a jingle, saves it, and plays it.
- `play_history.py` plays a file from `history/`.
- `api_connections/open_mateo.py` looks up a zip code and today's forecast.
- `classes/jingle.py` writes the lead, the rhythm chords, and the bass, then renders them with [blip8](https://pypi.org/project/blip8/).
- `const/weather_scale_mappings.py` holds the weather names, the scales, and the wind tempo steps.

Pitches come from [music21](https://www.music21.org/). Weather data is from [Open-Meteo](https://open-meteo.com/).
