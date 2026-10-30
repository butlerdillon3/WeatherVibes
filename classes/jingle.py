"""A short chiptune jingle in the scale for a weather code.

music21 supplies the pitches. A jingle states one singable shape three
times — the earworm — then falls home. The weather scale colors the shape.
"""

from __future__ import annotations

import json
import random
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import blip8
from blip8 import Samples
from music21 import scale
from music21.scale import ConcreteScale

from classes.blip8 import Blip8
from const.weather_scale_mappings import WEATHER_NAMES, WEATHER_SCALES, bpm_for_gust

HISTORY_DIR = Path(__file__).resolve().parent.parent / "history"

# blip8 accepts naturals, one sharp, or one flat. music21 sometimes spells
# the same pitch as E# or Fb, so store MIDI pitch classes and print sharps.
_SHARP_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_PC = {name: index for index, name in enumerate(_SHARP_NAMES)}

ScaleBuilder = Callable[[str], ConcreteScale]
Event = tuple[str | None, int]

# Chord roots for the three statements of the hook, then home.
_PROGRESSIONS = (
    (1, 4, 5, 1),
    (1, 5, 4, 1),
    (1, 1, 5, 1),
    (1, 4, 1, 1),
    (1, 2, 5, 1),
    (1, 5, 1, 1),
)
# One bar of the hook, in chord tones: 1 root, 3 third, 5 fifth, 2 the step above the root.
# The same shape is sung three times. A leap or a repeated note is the part you remember.
_MOTIFS = (
    ((1, 4), (3, 4), (5, 4), (3, 4)),
    ((1, 4), (1, 4), (5, 4), (3, 4)),
    ((5, 4), (3, 4), (1, 4), (3, 4)),
    ((1, 4), (2, 4), (3, 4), (5, 4)),
    ((1, 8), (5, 4), (3, 4)),
    ((1, 2), (1, 2), (3, 2), (5, 2), (3, 4), (1, 4)),
    ((1, 3), (3, 1), (5, 4), (3, 4), (1, 4)),
    ((5, 2), (3, 2), (1, 4), (2, 4), (3, 4)),
    ((1, 6), (3, 2), (5, 4), (3, 4)),
    ((1, 4), (5, 4), (3, 4), (5, 4)),
)
# The button. 0 is the scale step just under the tonic. The last note is home.
_TAGS = (
    ((5, 4), (3, 4), (1, 8)),
    ((5, 2), (4, 2), (3, 2), (2, 2), (1, 8)),
    ((5, 4), (1, 12)),
    ((2, 4), (1, 12)),
    ((0, 4), (1, 12)),
)

Hit = tuple[tuple[str, ...] | None, int]


def _pentatonic_major(tonic: str) -> ConcreteScale:
    return scale.OctaveRepeatingScale(tonic, ["M2", "M2", "m3", "M2", "m3"])


def _pentatonic_minor(tonic: str) -> ConcreteScale:
    return scale.OctaveRepeatingScale(tonic, ["m3", "M2", "M2", "m3", "M2"])


def _diminished(tonic: str) -> ConcreteScale:
    # Half-whole octatonic, the diminished scale.
    return scale.OctatonicScale(tonic, mode="m2")


SCALES: dict[str, ScaleBuilder] = {
    "major": scale.MajorScale,
    "minor": scale.MinorScale,
    "dorian": scale.DorianScale,
    "phrygian": scale.PhrygianScale,
    "lydian": scale.LydianScale,
    "mixolydian": scale.MixolydianScale,
    "locrian": scale.LocrianScale,
    "harmonic_minor": scale.HarmonicMinorScale,
    "whole_tone": scale.WholeToneScale,
    "pentatonic_major": _pentatonic_major,
    "pentatonic_minor": _pentatonic_minor,
    "diminished": _diminished,
}


def _blip_name(midi: int) -> str:
    """Spell a MIDI note the way blip8 reads it."""
    return f"{_SHARP_NAMES[midi % 12]}{midi // 12 - 1}"


def _midi_of(name: str) -> int:
    if len(name) >= 2 and name[1] == "#":
        pc = _PC[name[:2]]
        octave = int(name[2:])
    else:
        pc = _PC[name[0]]
        octave = int(name[1:])
    return (octave + 1) * 12 + pc


def _parse_pattern(pattern: str) -> list[Event]:
    tokens = pattern.split()
    events: list[Event] = []
    index = 0
    while index < len(tokens):
        length = 1
        while index + length < len(tokens) and tokens[index + length] == ".":
            length += 1
        token = tokens[index]
        events.append((None if token == "-" else token, length))
        index += length
    return events


def _as_pattern(events: list[Event]) -> str:
    tokens: list[str] = []
    for name, length in events:
        tokens.append("-" if name is None else name)
        tokens.extend(["."] * (length - 1))
    return " ".join(tokens)


def _hit_pattern(hits: list[Hit]) -> str:
    tokens: list[str] = []
    for chord, length in hits:
        tokens.append("-" if chord is None else chord[0])
        tokens.extend(["."] * (length - 1))
    return " ".join(tokens)


def _chords_by_bar(hits: list[Hit]) -> list[tuple[str, ...]]:
    """The first chord sounded in each bar."""
    found: dict[int, tuple[str, ...]] = {}
    position = 0
    for chord, length in hits:
        bar = position // 16
        if chord is not None and bar not in found:
            found[bar] = chord
        position += length
    if not found:
        return []
    return [found[bar] for bar in range(max(found) + 1) if bar in found]


class Jingle:
    """Builds a lead, a rhythm synth, and a ringing bass line for one weather code."""

    def __init__(
        self,
        weather_code: int,
        *,
        tonic: str = "C4",
        bars: int = 4,
        seed: int | None = None,
        synth: Blip8 | None = None,
        bpm: float = 120,
        wind_gust: float | None = None,
        volume: float = 0.35,
        duty: float = 0.25,
    ) -> None:
        try:
            scale_name = WEATHER_SCALES[weather_code]
        except KeyError:
            codes = ", ".join(str(code) for code in sorted(WEATHER_SCALES))
            raise ValueError(f"Unknown weather code {weather_code}. Choose from: {codes}.") from None
        try:
            build = SCALES[scale_name]
        except KeyError:
            raise ValueError(f"No music21 scale for {scale_name!r}.") from None
        if bars < 1:
            raise ValueError(f"A jingle needs at least one bar, got {bars}.")

        self.weather_code = weather_code
        self.scale_name = scale_name
        self.tonic = tonic
        self.bars = bars
        self.seed = seed
        self.wind_gust = wind_gust
        self.swing = 0.0
        self.synth = synth if synth is not None else Blip8(
            bpm=bpm_for_gust(wind_gust, bpm),
            volume=volume,
            duty=duty,
        )
        self._scale = build(tonic)
        self._rng = random.Random(seed)
        self._pcs = self._pitch_classes(self._span("P8"))
        self.lead_line = ""
        self.melody_line = ""
        self.rhythm_line = ""
        self.bass_line = ""
        self.chord_line = ""

    def notes(self) -> list[str]:
        """Pitches of this weather's scale, from the tonic up through the octave."""
        return self._span("P8")

    def build(self) -> Samples:
        """Write lead, rhythm, and bass in the weather scale.

        Pass seed to repeat the same jingle. The lead resolves to the tonic.
        High wind has already been added to the tempo. Swing is saved with the
        jingle so a replay has the same feel.
        """
        if self.seed is not None:
            self._rng.seed(self.seed)
        self.swing = self._rng.choice((0.0, 0.0, 0.0, 0.04))
        bass, degrees = self._arrange()
        rhythm = self._rhythm(degrees)
        pool = self._lead_pool()
        lead = self._compose(pool, degrees)
        self._lead_events = lead
        self._lead_notes = pool
        self._rhythm_hits = rhythm
        self._bass_events = bass
        self.lead_line = _as_pattern(lead)
        self.melody_line = self.lead_line
        self.rhythm_line = _hit_pattern(rhythm)
        self.bass_line = _as_pattern(bass)
        self.chord_line = " | ".join(" ".join(chord) for chord in _chords_by_bar(rhythm))
        return self.synth.layer(
            self._render_lead(lead, pool),
            self._render_rhythm(rhythm),
            self._render_bass(bass),
        )

    def play(self) -> None:
        """Build a jingle and play it through the speakers."""
        self.synth.play(self.build())

    def save(self, directory: Path | None = None) -> Path:
        """Write this jingle to history as JSON. Build it first."""
        if not self.lead_line:
            raise RuntimeError("Build the jingle before saving it.")
        folder = HISTORY_DIR if directory is None else directory
        folder.mkdir(parents=True, exist_ok=True)
        moment = datetime.now().astimezone()
        stamp = moment.strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3]
        weather = WEATHER_NAMES.get(self.weather_code, str(self.weather_code))
        path = folder / f"{stamp}_{weather.replace(' ', '_')}_{self.scale_name}.json"
        record = {
            "timestamp": moment.isoformat(timespec="seconds"),
            "weather": weather,
            "weather_code": self.weather_code,
            "scale": self.scale_name,
            "tonic": self.tonic,
            "bars": self.bars,
            "bpm": self.synth.bpm,
            "swing": self.swing,
            "wind_gust": self.wind_gust,
            "volume": self.synth.volume,
            "duty": self.synth.duty,
            "seed": self.seed,
            "lead_pool": self._lead_notes,
            "lead": self.lead_line,
            "rhythm_line": self.rhythm_line,
            "bass": self.bass_line,
            "chords": self.chord_line,
            "rhythm": [
                {"notes": list(chord) if chord is not None else None, "sixteenths": length}
                for chord, length in self._rhythm_hits
            ],
        }
        path.write_text(json.dumps(record, indent=2) + "\n")
        return path

    @classmethod
    def play_file(cls, path: Path) -> None:
        """Play a jingle saved by save()."""
        record = json.loads(path.read_text())
        jingle = cls(
            record["weather_code"],
            tonic=record["tonic"],
            bars=record["bars"],
            bpm=record["bpm"],
            volume=record["volume"],
            duty=record["duty"],
            seed=record.get("seed"),
        )
        jingle.swing = float(record.get("swing", 0.0))
        rhythm: list[Hit] = [
            (tuple(hit["notes"]) if hit["notes"] is not None else None, hit["sixteenths"])
            for hit in record["rhythm"]
        ]
        tune = jingle.synth.layer(
            jingle._render_lead(_parse_pattern(record["lead"]), record["lead_pool"]),
            jingle._render_rhythm(rhythm),
            jingle._render_bass(_parse_pattern(record["bass"])),
        )
        jingle.synth.play(tune)

    def _span(self, top: str) -> list[str]:
        low = self._scale.pitchFromDegree(1)
        return self._collect(low, low.transpose(top))

    def _lead_pool(self) -> list[str]:
        """The scale an octave above the tonic, where the lead plays."""
        low = self._scale.pitchFromDegree(1).transpose("P8")
        return self._collect(low, low.transpose("P15"))

    def _collect(self, low, high) -> list[str]:
        names: list[str] = []
        for pitch in self._scale.getPitches(low, high):
            name = _blip_name(int(pitch.midi))
            if name not in names:
                names.append(name)
        return names

    def _pitch_classes(self, names: list[str]) -> list[int]:
        pcs: list[int] = []
        for name in names:
            pc = _midi_of(name) % 12
            if pc not in pcs:
                pcs.append(pc)
        return pcs

    def _named(self, degree: int, octave: int) -> str:
        pitch = self._scale.pitchFromDegree(degree)
        return _blip_name((octave + 1) * 12 + int(pitch.midi) % 12)

    def _arrange(self) -> tuple[list[Event], list[int]]:
        """Roots on the beat, fifths in between, and a tonic that rings at the end."""
        degrees = self._degrees()
        bounce = self._rng.random() < 0.5
        events: list[Event] = []
        for bar, degree in enumerate(degrees):
            if bar == len(degrees) - 1:
                events.append((self._named(1, 2), 16))
                break
            root, fifth = self._bass_tones(degree)
            if bounce:
                events.extend([(root, 4), (fifth, 4), (root, 4), (fifth, 4)])
            else:
                events.extend([(root, 8), (fifth, 8)])
        return events, degrees

    def _degrees(self) -> list[int]:
        count = len(self._pcs)
        pattern = self._rng.choice(_PROGRESSIONS)

        def fit(degree: int) -> int:
            if 1 <= degree <= count:
                return degree
            return ((degree - 1) % count) + 1

        if self.bars == 1:
            return [1]
        body = [fit(degree) for degree in pattern[:-1]]
        while len(body) < self.bars - 1:
            body.extend(fit(degree) for degree in pattern[:-1])
        return body[: self.bars - 1] + [1]

    def _bass_tones(self, degree: int) -> tuple[str, str]:
        root = self._named(degree, 2)
        fifth_pc = self._chord_pcs(degree)[2]
        fifth_midi = (2 + 1) * 12 + fifth_pc
        if fifth_midi <= _midi_of(root):
            fifth_midi += 12
        return root, _blip_name(fifth_midi)

    def _chord_pcs(self, degree: int) -> list[int]:
        index = degree - 1
        count = len(self._pcs)
        return [self._pcs[(index + offset) % count] for offset in (0, 2, 4)]

    def _rhythm_chord(self, degree: int) -> list[str]:
        """Stack the bar's chord under the lead, in a closed voicing."""
        pcs = self._chord_pcs(degree)
        ceiling = int(self._scale.pitchFromDegree(1).midi) + 10
        midi = (4 + 1) * 12 + pcs[0]
        voiced = [midi]
        for pc in pcs[1:]:
            midi += 1
            while midi % 12 != pc:
                midi += 1
            voiced.append(midi)
        while voiced[-1] > ceiling and voiced[0] - 12 >= 48:
            voiced = [tone - 12 for tone in voiced]
        return [_blip_name(tone) for tone in voiced]

    def _rhythm(self, degrees: list[int]) -> list[Hit]:
        """Chords on beats 1 and 3, then one button under the last note."""
        hits: list[Hit] = []
        for bar, degree in enumerate(degrees):
            chord = tuple(self._rhythm_chord(degree))
            light = chord[:2]
            if self.bars > 1 and bar == len(degrees) - 1:
                hits.extend([(chord, 4), (None, 12)])
                continue
            hits.extend([(chord, 4), (None, 4), (light, 4), (None, 4)])
        return hits

    def _compose(self, pool: list[str], degrees: list[int]) -> list[Event]:
        """Sing one shape three times, then fall to the tonic.

        The shape is the same every time. The chord under it changes, and the
        third time the last note pops up an octave. That is the hook.
        """
        motif = self._rng.choice(_MOTIFS)
        tag = self._rng.choice(_TAGS)
        sparkle = self._rng.random() < 0.65
        events: list[Event] = []
        for bar, degree in enumerate(degrees):
            if bar == len(degrees) - 1:
                events.extend(self._tag(tag, pool))
                break
            lift = sparkle and bar == len(degrees) - 2
            events.extend(self._motif(motif, degree, pool, lift))
        return events

    def _motif(
        self,
        motif: tuple[tuple[int, int], ...],
        degree: int,
        pool: list[str],
        lift_last: bool,
    ) -> list[Event]:
        tones = self._chord_voice(degree)
        events: list[Event] = []
        for rel, duration in motif:
            midi = tones[rel]
            events.append((self._from_pool(midi, pool), duration))
        if lift_last:
            name, duration = events[-1]
            lifted_midi = _midi_of(name) + 12
            lifted = _blip_name(lifted_midi)
            if lifted in pool:
                events[-1] = (lifted, duration)
        return events

    def _chord_voice(self, degree: int) -> dict[int, int]:
        """Root, step, third, and fifth, stacked upward from octave 5."""
        root_pc, third_pc, fifth_pc = (
            self._chord_pcs(degree)[0],
            self._chord_pcs(degree)[1],
            self._chord_pcs(degree)[2],
        )
        passing = self._pcs[degree % len(self._pcs)]
        root = (5 + 1) * 12 + root_pc

        def stacked(pc: int) -> int:
            midi = root
            while midi % 12 != pc:
                midi += 1
            return midi

        return {1: root, 2: stacked(passing), 3: stacked(third_pc), 5: stacked(fifth_pc)}

    def _tag(self, tag: tuple[tuple[int, int], ...], pool: list[str]) -> list[Event]:
        """The button: a short fall, or a step into the high tonic."""
        high = any(degree == 0 for degree, _ in tag)
        events: list[Event] = []
        for degree, duration in tag:
            octave = 6 if high else 5
            events.append((self._key_note(degree, octave, pool), duration))
        return events

    def _key_note(self, degree: int, octave: int, pool: list[str]) -> str:
        tonic_pc = self._pcs[0]
        if degree == 0:
            pc = self._pcs[-1]
            midi = (octave + 1) * 12 + pc
            tonic_midi = (octave + 1) * 12 + tonic_pc
            if midi >= tonic_midi:
                midi -= 12
        else:
            count = len(self._pcs)
            if degree > count:
                degree = ((degree - 1) % count) + 1
            midi = (octave + 1) * 12 + self._pcs[degree - 1]
        return self._from_pool(midi, pool)

    def _from_pool(self, midi: int, pool: list[str]) -> str:
        name = _blip_name(midi)
        if name in pool:
            return name
        same = [note for note in pool if _midi_of(note) % 12 == midi % 12]
        if not same:
            return pool[0]
        return min(same, key=lambda note: abs(_midi_of(note) - midi))

    def _onsets(self, sixteenths: int) -> list[float]:
        """Start time of each sixteenth. Offbeats sit a little late when the tune swings."""
        step = 60.0 / self.synth.bpm / 4.0
        times: list[float] = []
        for index in range(sixteenths + 1):
            place = index % 4
            if place == 2:
                delay = self.swing * step * 2
            elif place in (1, 3):
                delay = self.swing * step * 0.4
            else:
                delay = 0.0
            times.append(index * step + delay)
        return times

    def _render_lead(self, events: list[Event], pool: list[str]) -> Samples:
        times = self._onsets(sum(length for _, length in events))
        layers: list[Samples] = []
        position = 0
        previous: str | None = None
        for index, (name, length) in enumerate(events):
            start = times[position]
            span = max(0.04, times[position + length] - start)
            if name is not None:
                final = all(later is None for later, _ in events[index + 1 :])
                nxt = events[index + 1][0] if index + 1 < len(events) else None
                connected = nxt is not None and self._neighbors(pool, name, nxt)
                if final:
                    release = max(0.35, 60.0 / self.synth.bpm * 1.5)
                    body = span
                elif connected:
                    release = min(0.16, span * 0.4)
                    body = span
                else:
                    release = min(0.06, span * 0.18)
                    body = span * 0.8
                gap = 0 if previous is None else abs(pool.index(name) - pool.index(previous))
                scoop = _blip_name(_midi_of(name) - 1) if length >= 4 and (previous is None or gap >= 3) else None
                level = self.synth.volume * self._expression(length, position, gap)
                layers.append(self.synth.at(start, self._sung(name, body, release, level, scoop)))
                previous = name
            position += length
        if not layers:
            return self.synth.silence(times[-1])
        return self.synth.layer(*layers)

    def _expression(self, length: int, position: int, gap: int) -> float:
        """Louder on downbeats, long notes, and the note that lands a leap."""
        amount = 0.88
        if position % 16 == 0:
            amount += 0.08
        elif position % 4 == 2:
            amount += 0.04
        if length >= 8:
            amount += 0.05
        if gap >= 3:
            amount += 0.08
        elif gap == 0:
            amount -= 0.07
        return min(1.08, max(0.74, amount))

    def _sung(self, name: str, body: float, release: float, level: float, scoop: str | None) -> Samples:
        """A round lead with a little pulse, and a short scoop into phrases and leaps."""
        total = body + release
        sine = level * 0.54
        edge = level * 0.2
        freq = self.synth.note(name)
        if scoop is not None and body > 0.1:
            glide = min(0.055, body * 0.25)
            start = self.synth.note(scoop)
            head = self.synth.layer(
                self.synth.wavetable(blip8.SINE_TABLE, (start, freq), glide, volume=sine),
                self.synth.square((start, freq), glide, duty=0.25, volume=edge),
            )
            tail = self.synth.layer(
                self.synth.wavetable(blip8.SINE_TABLE, freq, total - glide, volume=sine),
                self.synth.square(freq, total - glide, duty=0.25, volume=edge),
            )
            tone = self.synth.sequence(head, tail)
            attack = 0.006
        else:
            tone = self.synth.layer(
                self.synth.wavetable(blip8.SINE_TABLE, freq, total, volume=sine),
                self.synth.square(freq, total, duty=0.25, volume=edge),
            )
            attack = 0.02 if body >= 0.25 else 0.008
        return self.synth.envelope(
            tone,
            attack=attack,
            decay=min(0.07, max(0.01, body * 0.22)),
            sustain=0.58 if body >= 0.25 else 0.76,
            release=release,
        )

    def _render_bass(self, events: list[Event]) -> Samples:
        """Let each bass note fade for a while after the next one has started."""
        times = self._onsets(sum(length for _, length in events))
        layers: list[Samples] = []
        position = 0
        for name, length in events:
            start = times[position]
            span = max(0.05, times[position + length] - start)
            if name is not None:
                release = span * 0.55
                tone = self.synth.triangle(
                    self.synth.note(name),
                    span + release,
                    volume=self.synth.volume * (0.66 if length >= 8 else 0.5),
                )
                shaped = self.synth.envelope(
                    tone,
                    attack=0.03,
                    decay=span * 0.3,
                    sustain=0.68,
                    release=release,
                )
                layers.append(self.synth.at(start, shaped))
            position += length
        if not layers:
            return self.synth.silence(times[-1])
        return self.synth.layer(*layers)

    def _render_rhythm(self, hits: list[Hit]) -> Samples:
        """Short chord stabs. Downbeats are fuller; offbeats are thinner."""
        times = self._onsets(sum(length for _, length in hits))
        layers: list[Samples] = []
        position = 0
        for chord, length in hits:
            start = times[position]
            span = max(0.04, times[position + length] - start)
            if chord is not None:
                strong = position % 8 == 0
                release = min(0.05, span * 0.2)
                decay = min(0.06, span * 0.45)
                volume = self.synth.volume * (0.2 if strong else 0.13)
                for name in chord:
                    tone = self.synth.square(
                        self.synth.note(name),
                        span + release,
                        duty=0.5,
                        volume=volume,
                    )
                    shaped = self.synth.envelope(
                        tone, attack=0.004, decay=decay, sustain=0.4 if strong else 0.22, release=release
                    )
                    layers.append(self.synth.at(start, shaped))
            position += length
        if not layers:
            return self.synth.silence(times[-1])
        return self.synth.layer(*layers)

    def _neighbors(self, pool: list[str], this: str, nxt: str) -> bool:
        try:
            return abs(pool.index(this) - pool.index(nxt)) <= 1
        except ValueError:
            return abs(_midi_of(this) - _midi_of(nxt)) <= 2
