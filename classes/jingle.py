"""A short chiptune jingle in the scale for a weather code.

music21 supplies the pitches. The tune is a short phrase stated, then sung
again a step higher, then brought home. The bass walks other degrees of that
same scale, and each bar's chord is built on the bass note that falls on beat one.
"""

from __future__ import annotations

import random
from collections.abc import Callable

import blip8
from blip8 import Samples
from music21 import scale
from music21.scale import ConcreteScale

from classes.blip8 import Blip8
from const.weather_scale_mappings import WEATHER_SCALES

# blip8 accepts naturals, one sharp, or one flat. music21 sometimes spells
# the same pitch as E# or Fb, so store MIDI pitch classes and print sharps.
_SHARP_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_PC = {name: index for index, name in enumerate(_SHARP_NAMES)}

ScaleBuilder = Callable[[str], ConcreteScale]
Event = tuple[str | None, int]

# One bar of sixteenths. The phrase reuses one of these so the rhythm can be recognized.
_CELLS = (
    (2, 2, 4, 4, 4),
    (6, 2, 4, 4),
    (4, 2, 2, 4, 4),
    (2, 2, 2, 2, 8),
    (4, 4, 2, 2, 4),
    (8, 4, 4),
    (2, 2, 4, 8),
    (4, 4, 8),
)
_CADENCES = (
    (4, 4, 8),
    (2, 2, 4, 8),
    (4, 2, 2, 8),
    (8, 8),
    (2, 2, 2, 2, 8),
)
# Scale steps after the first note: lift, then settle.
_CONTOURS = (
    (1, 1, 2, -1, -1),
    (1, 2, -1, 1, -2),
    (2, -1, 1, 1, -1),
    (1, 1, 0, 2, -1),
    (1, 2, 1, -1, -2),
    (2, 1, -1, -1),
    (1, 1, 2, -2),
)

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


def _as_pattern(events: list[Event]) -> str:
    tokens: list[str] = []
    for name, length in events:
        tokens.append("-" if name is None else name)
        tokens.extend(["."] * (length - 1))
    return " ".join(tokens)


def _breathe(events: list[Event]) -> list[Event]:
    """Leave a short rest at the end of a phrase so the next one can answer."""
    name, duration = events[-1]
    if name is None or duration < 4:
        return events
    return events[:-1] + [(name, duration - 2), (None, 2)]


class Jingle:
    """Builds a phrase, chords, and a ringing bass line for one weather code."""

    def __init__(
        self,
        weather_code: int,
        *,
        tonic: str = "C4",
        bars: int = 4,
        seed: int | None = None,
        synth: Blip8 | None = None,
        bpm: float = 120,
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
        self.synth = synth if synth is not None else Blip8(bpm=bpm, volume=volume, duty=duty)
        self._scale = build(tonic)
        self._rng = random.Random(seed)
        self._pcs = self._pitch_classes(self._span("P8"))
        self.melody_line = ""
        self.bass_line = ""
        self.chord_line = ""

    def notes(self) -> list[str]:
        """Pitches of this weather's scale, from the tonic up through the octave."""
        return self._span("P8")

    def build(self) -> Samples:
        """Write a phrase over a walking bass line and the chords those notes make.

        Pass seed to repeat the same jingle. Melody and bass both start and end
        on the tonic, and every bass note belongs to the weather scale.
        """
        if self.seed is not None:
            self._rng.seed(self.seed)
        pool = self._span("P15")
        bass, degrees = self._walking_bass()
        melody = self._compose(pool, degrees)
        self.melody_line = _as_pattern(melody)
        self.bass_line = _as_pattern(bass)
        self.chord_line = " | ".join(" ".join(self._chord_names(degree)) for degree in degrees)
        return self.synth.layer(
            self._render_melody(melody, pool),
            self._render_bass(bass),
            self._render_chords(degrees),
        )

    def play(self) -> None:
        """Build a jingle and play it through the speakers."""
        self.synth.play(self.build())

    def _span(self, top: str) -> list[str]:
        low = self._scale.pitchFromDegree(1)
        names: list[str] = []
        for pitch in self._scale.getPitches(low, low.transpose(top)):
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

    def _walking_bass(self) -> tuple[list[Event], list[int]]:
        """Step through the scale in whole and half notes, then come home.

        The degree list is one chord per bar, taken from the note on beat one.
        """
        if self.bars == 1:
            return [(self._named(1, 2), 16)], [1]

        index = 0
        events: list[Event] = []
        roots: list[int] = []
        for _ in range(self.bars - 1):
            roots.append(index + 1)
            if self._rng.random() < 0.55:
                events.append((self._named(index + 1, 2), 8))
                index = self._step_degree(index)
                events.append((self._named(index + 1, 2), 8))
            else:
                events.append((self._named(index + 1, 2), 16))
            index = self._step_degree(index)

        if index == 0:
            roots.append(1)
            events.append((self._named(1, 2), 16))
        else:
            roots.append(index + 1)
            events.append((self._named(index + 1, 2), 8))
            events.append((self._named(1, 2), 8))
        return events, roots

    def _step_degree(self, index: int) -> int:
        count = len(self._pcs)
        step = self._rng.choice((-2, -1, -1, 1, 1, 1, 2))
        landed = index + step
        if landed < 0 or landed >= count:
            landed = index - step
        return max(0, min(count - 1, landed))

    def _chord_pcs(self, degree: int) -> list[int]:
        index = degree - 1
        count = len(self._pcs)
        return [self._pcs[(index + offset) % count] for offset in (0, 2, 4)]

    def _chord_names(self, degree: int) -> list[str]:
        """Stack the chord in the third octave, with the top note opened up."""
        pcs = self._chord_pcs(degree)
        midi = (3 + 1) * 12 + pcs[0]
        voiced = [midi]
        for pc in pcs[1:]:
            midi += 1
            while midi % 12 != pc:
                midi += 1
            voiced.append(midi)
        if voiced[-1] - voiced[0] < 12:
            voiced[-1] += 12
        return [_blip_name(tone) for tone in voiced]

    def _chord_indices(self, pool: list[str], degree: int) -> list[int]:
        pcs = set(self._chord_pcs(degree))
        return [index for index, name in enumerate(pool) if _midi_of(name) % 12 in pcs]

    def _compose(self, pool: list[str], degrees: list[int]) -> list[Event]:
        if self.bars == 1:
            return self._cadence(pool, 0, self._rng.choice(_CADENCES))

        cell = self._rng.choice(_CELLS)
        contour = self._fit_contour(len(cell) - 1)
        events: list[Event] = []
        last_index = 0
        phrase_end = max(0, self.bars // 2 - 1)
        for bar in range(self.bars - 1):
            start = 0 if bar % 2 == 0 else min(len(pool) - 1, 1)
            indices = self._sing(pool, start, contour, cell, degrees[bar])
            bar_events = [(pool[index], duration) for index, duration in zip(indices, cell, strict=True)]
            if bar == phrase_end:
                bar_events = _breathe(bar_events)
            events.extend(bar_events)
            last_index = indices[-1]
        events.extend(self._cadence(pool, last_index, self._rng.choice(_CADENCES)))
        return events

    def _fit_contour(self, needed: int) -> tuple[int, ...]:
        contour = self._rng.choice(_CONTOURS)
        if needed <= len(contour):
            return contour[:needed]
        steps = list(contour)
        while len(steps) < needed:
            steps.append(self._rng.choice((-1, -1, 1, 0)))
        return tuple(steps)

    def _sing(
        self,
        pool: list[str],
        start: int,
        contour: tuple[int, ...],
        durations: tuple[int, ...],
        degree: int,
    ) -> list[int]:
        """Follow the contour, and lean long notes toward a chord tone."""
        targets = self._chord_indices(pool, degree)
        index = start
        indices: list[int] = []
        position = 0
        for step, duration in enumerate(durations):
            if step:
                index = max(0, min(len(pool) - 1, index + contour[step - 1]))
            if step and targets and (position % 8 == 0 or duration >= 8):
                nearest = min(targets, key=lambda target: (abs(target - index), target))
                if abs(nearest - index) <= 1:
                    index = nearest
            indices.append(index)
            position += duration
        return indices

    def _cadence(self, pool: list[str], start: int, durations: tuple[int, ...]) -> list[Event]:
        end = self._nearest_tonic(pool, start)
        begin = min(len(pool) - 1, end + 1) if start == end else start
        count = len(durations)
        indices: list[int] = []
        for step in range(count):
            if count == 1:
                index = end
            else:
                index = begin + (end - begin) * step // (count - 1)
            indices.append(max(0, min(len(pool) - 1, index)))
        indices[-1] = end
        return [(pool[index], duration) for index, duration in zip(indices, durations, strict=True)]

    def _nearest_tonic(self, pool: list[str], index: int) -> int:
        tonic = _midi_of(pool[0]) % 12
        targets = [i for i, name in enumerate(pool) if _midi_of(name) % 12 == tonic]
        return min(targets, key=lambda target: (abs(target - index), target))

    def _render_melody(self, events: list[Event], pool: list[str]) -> Samples:
        step = 60.0 / self.synth.bpm / 4.0
        beat = step * 4
        layers: list[Samples] = []
        position = 0
        clock = 0.0
        for index, (name, length) in enumerate(events):
            if name is not None:
                duration = step * length
                nxt = events[index + 1][0] if index + 1 < len(events) else None
                release = beat * (0.42 if nxt and self._neighbors(pool, name, nxt) else 0.16)
                if all(later is None for later, _ in events[index + 1 :]):
                    release = max(release, beat * 2.2)
                # A zero decay would jump from the attack peak straight to the sustain level.
                decay = beat * (0.16 if length >= 4 else 0.05)
                sustain = 0.58 if length >= 4 else 0.84
                accent = 1.06 if position % 16 == 0 else 1.0
                tone = self.synth.square(
                    self.synth.note(name),
                    duration + release,
                    duty=self.synth.duty,
                    volume=self.synth.volume * 0.78 * accent,
                )
                shaped = self.synth.envelope(
                    tone, attack=0.012, decay=decay, sustain=sustain, release=release
                )
                layers.append(self.synth.at(clock, shaped))
            position += length
            clock += step * length
        return self.synth.layer(*layers)

    def _render_bass(self, events: list[Event]) -> Samples:
        """Let each bass note fade for a while after the next one has started."""
        step = 60.0 / self.synth.bpm / 4.0
        layers: list[Samples] = []
        clock = 0.0
        for name, length in events:
            if name is None:
                clock += step * length
                continue
            duration = step * length
            release = duration * 0.7
            tone = self.synth.triangle(
                self.synth.note(name),
                duration + release,
                volume=self.synth.volume * 0.58,
            )
            shaped = self.synth.envelope(
                tone,
                attack=0.04,
                decay=duration * 0.28,
                sustain=0.7,
                release=release,
            )
            layers.append(self.synth.at(clock, shaped))
            clock += duration
        return self.synth.layer(*layers)

    def _render_chords(self, degrees: list[int]) -> Samples:
        step = 60.0 / self.synth.bpm / 4.0
        bar = step * 16
        release = bar * 0.3
        layers: list[Samples] = []
        for index, degree in enumerate(degrees):
            for name in self._chord_names(degree):
                tone = self.synth.wavetable(
                    blip8.BELL_TABLE,
                    self.synth.note(name),
                    bar + release,
                    volume=self.synth.volume * 0.14,
                )
                shaped = self.synth.envelope(
                    tone,
                    attack=0.08,
                    decay=bar * 0.34,
                    sustain=0.42,
                    release=release,
                )
                layers.append(self.synth.at(index * bar, shaped))
        return self.synth.layer(*layers)

    def _neighbors(self, pool: list[str], this: str, nxt: str) -> bool:
        try:
            return abs(pool.index(this) - pool.index(nxt)) <= 1
        except ValueError:
            return abs(_midi_of(this) - _midi_of(nxt)) <= 2
