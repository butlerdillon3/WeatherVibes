# WeatherVibes

WeatherVibes turns today's weather into music. `GENERATOR` at the top of `main.py` chooses which one.

- `"ai"` writes a MusicGen clip. The forecast becomes the prompt: place, condition, high, low, wind, a recommended scale, and a tempo. A genre is picked at random for each run.
- `"programatic"` writes an 8-bit jingle. The weather code picks a musical scale, and the day's maximum wind gust can speed the tempo up. The lead sings one small shape three times, the chords under it change, and the last bar falls to the tonic and holds it.

The zip code is looked up once on [Open-Meteo](https://open-meteo.com/). That forecast is passed into `AiMusicGen` or `Jingle`. `ZIP_CODE` in `main.py` is `11215`. Change that string to hear somewhere else.

## Run

Python 3.14 or newer, with [Poetry](https://python-poetry.org/).

```bash
poetry install
poetry run python main.py
```

The script prints the forecast. An AI run then logs the genre, scale, tempo, and prompt, and saves a wav. A programmatic run prints the scale, tempo, and lead, rhythm, and bass lines, saves a wav, and plays it through the speakers.

## GPU and the model

The AI generator needs an NVIDIA GPU. The jingle generator does not. PyTorch's CUDA libraries come with the project, so you do not install the CUDA toolkit yourself. You do need a current NVIDIA driver. `nvidia-smi` should print the GPU name before you install anything else.

`poetry install` downloads PyTorch from the CUDA 13.2 index in `pyproject.toml`, not the CPU build on PyPI. Check that from the project folder:

```bash
poetry run python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

The version should end in `+cu132`, CUDA should be `True`, and the last line should be your GPU. A version ending in `+cpu` means the CUDA wheel was not installed. Run `poetry install` again from this folder so Poetry uses the `pytorch-cu132` source.

`poetry run` is the interpreter that has that wheel. If you press Play in the editor and torch is missing, point the editor at the environment from `poetry env info -p`.

Set `GENERATOR = "ai"` and run `main.py`. The first run downloads `facebook/musicgen-large` into `model-cache/` next to the script. That is about 14 GB, and it is not committed. Later runs use the cache. The clip is generated in float16. A 16 GB GPU is enough for the 25 second clip.

A Hugging Face token is optional. Without one, the download still works, and the log warns that the request is unauthenticated. To raise the rate limit, set `HF_TOKEN` in the environment before the run.

On Windows, Smart App Control can block the PyTorch CUDA libraries. The message is `WinError 4551` while importing torch, and the file is `c10_cuda.dll` or another file in `torch\lib`. Turn Smart App Control off under Windows Security, App & browser control, Smart App Control settings. Windows will not let you turn it back on without reinstalling Windows.

## Play a saved clip

New files are wavs named with the date, time, place, and weather, for example `2026-11-18T17-14-30-624_Brooklyn_Clear_sky.wav`.

- AI clips are written to `weather_clips/`.
- Jingles are written to `history/`.
- Older jingles are still JSON in `history/`, named with the time, the weather, and the scale, for example `2026-10-30T14-04-30-230_Clear_sky_major.json`.

Those files stay on your machine and are not committed.

```bash
poetry run python play_history.py
poetry run python play_history.py --all
poetry run python play_history.py history/2026-10-30T14-04-30-230_Clear_sky_major.json
poetry run python play_history.py 2026-11-18T17-14-30-624_Brooklyn_Clear_sky.wav
```

With no arguments, the newest file plays. `--all` plays every saved file, oldest first. A bare file name is looked up in `history/` and then `weather_clips/`. A `.json` file is rebuilt as a jingle. A `.wav` file is played as recorded.

## How weather becomes music

The maps live in `const/weather_scale_mappings.py`.

The weather code chooses the scale. Clear sky is major. Fog is minor. Freezing rain leans phrygian or locrian. A thunderstorm with heavy hail is whole tone. The programmatic jingle uses the same shape every time, so the scale is what makes the day sound like itself. The AI prompt recommends that same scale.

The tempo starts at 120 bpm. Gusts under 25 mph leave it there. A strong breeze adds 10 bpm, a gale adds 30, and a hurricane adds 70. The gust is the day's maximum, in miles per hour.

## Layout

- `main.py` fetches the forecast once and passes it to the selected generator.
- `classes/ai_music_gen.py` builds a MusicGen prompt from the forecast and writes a wav.
- `classes/jingle.py` writes the lead, the rhythm chords, and the bass, then renders them with [blip8](https://pypi.org/project/blip8/).
- `classes/clip_path.py` names both wav files.
- `play_history.py` plays a wav from `history/` or `weather_clips/`, or rebuilds an older JSON jingle.
- `api_connections/open_mateo.py` looks up a zip code and today's forecast.
- `const/weather_scale_mappings.py` holds the weather names, the scales, and the wind tempo steps.

Pitches for the jingle come from [music21](https://www.music21.org/). The AI clips come from [MusicGen](https://github.com/facebookresearch/audiocraft). Weather data is from [Open-Meteo](https://open-meteo.com/).
