"""Chiptune sounds and music through the blip8 package.

blip8 generates NES- and Game Boy-style audio from waveforms. This class keeps
the tempo, volume, and square-wave duty used across a jingle, and exposes the
package's voices, patterns, ready-made effects, and playback.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import blip8
import blip8.sfx as sfx
from blip8 import Samples

Voice = Callable[..., Samples]

EFFECTS: dict[str, Callable[..., Samples]] = {
    "blip": sfx.blip,
    "select": sfx.select,
    "back": sfx.back,
    "coin": sfx.coin,
    "jump": sfx.jump,
    "powerup": sfx.powerup,
    "laser": sfx.laser,
    "hurt": sfx.hurt,
    "explosion": sfx.explosion,
    "chime": sfx.chime,
    "kick": sfx.kick,
    "snare": sfx.snare,
    "hat": sfx.hat,
    "crash": sfx.crash,
}


class Blip8:
    """Builds and plays chiptune audio with shared tempo, volume, and duty."""

    def __init__(self, bpm: float = 120, volume: float = 0.4, duty: float = 0.5) -> None:
        self.bpm = bpm
        self.volume = volume
        self.duty = duty

    def note(self, name: str) -> float:
        """Convert a note name to Hz: "A4" is 440."""
        return blip8.note(name)

    def square(
        self,
        freq: blip8.Pitch,
        length: float,
        *,
        duty: float | None = None,
        volume: float | None = None,
    ) -> Samples:
        """A pulse wave. duty 0.5 is hollow; 0.125 is thin and nasal."""
        return blip8.square(
            freq=freq,
            length=length,
            duty=self.duty if duty is None else duty,
            volume=self._volume(volume),
        )

    def triangle(
        self,
        freq: blip8.Pitch,
        length: float,
        *,
        volume: float | None = None,
    ) -> Samples:
        """A triangle wave, the softer bass voice."""
        return blip8.triangle(freq=freq, length=length, volume=self._volume(volume))

    def noise(
        self,
        length: float,
        *,
        volume: float | None = None,
        seed: int | None = None,
    ) -> Samples:
        """White noise for drums and weather. Pass seed to repeat the same noise."""
        return blip8.noise(length=length, volume=self._volume(volume), seed=seed)

    def wavetable(
        self,
        table: Samples | Sequence[float],
        freq: blip8.Pitch,
        length: float,
        *,
        volume: float | None = None,
    ) -> Samples:
        """A custom one-cycle shape. blip8.SINE_TABLE and blip8.BELL_TABLE are built in."""
        return blip8.wavetable(table, freq=freq, length=length, volume=self._volume(volume))

    def envelope(self, samples: Samples, **stages: float) -> Samples:
        """Shape volume over time. Stages are attack, decay, sustain, and release."""
        return blip8.envelope(samples, **stages)

    def crunch(self, samples: Samples, bits: int = 4) -> Samples:
        """Quantise to 2**bits levels. bits=4 matches the Game Boy wave channel."""
        return blip8.crunch(samples, bits=bits)

    def melody(
        self,
        pattern: str,
        *,
        bpm: float | None = None,
        voice: Voice | None = None,
        volume: float | None = None,
        **voice_options: object,
    ) -> Samples:
        """Play a pattern. "." holds the previous note and "-" rests.

        melody("C4 E4 G4 C5")
        melody("C2 . . . G2 . . .", voice=blip8.triangle)
        """
        voice, voice_options = self._voice(voice, voice_options)
        return blip8.melody(
            pattern,
            bpm=self.bpm if bpm is None else bpm,
            voice=voice,
            volume=self._volume(volume),
            **voice_options,
        )

    def chord(
        self,
        notes: str,
        length: float = 0.5,
        *,
        voice: Voice | None = None,
        volume: float | None = None,
        **voice_options: object,
    ) -> Samples:
        """Play several notes at once: chord("C4 E4 G4").

        Each note is quieter than a melody line so the summed chord stays in range.
        """
        voice, voice_options = self._voice(voice, voice_options)
        return blip8.chord(
            notes,
            length=length,
            voice=voice,
            volume=self.volume * 0.4 if volume is None else volume,
            **voice_options,
        )

    def arpeggio(
        self,
        notes: str,
        length: float = 0.5,
        rate: float = 0.025,
        *,
        voice: Voice | None = None,
        volume: float | None = None,
        **voice_options: object,
    ) -> Samples:
        """Cycle a chord's notes quickly enough that they fuse: arpeggio("C4 E4 G4")."""
        voice, voice_options = self._voice(voice, voice_options)
        return blip8.arpeggio(
            notes,
            length=length,
            rate=rate,
            voice=voice,
            volume=self._volume(volume),
            **voice_options,
        )

    def silence(self, length: float) -> Samples:
        """Return `length` seconds of silence."""
        return blip8.silence(length)

    def sequence(self, *sounds: Samples) -> Samples:
        """Join sounds end to end."""
        return blip8.sequence(*sounds)

    def at(self, time: float, sound: Samples) -> Samples:
        """Delay a sound so it starts `time` seconds in. Mix the results with layer()."""
        return blip8.at(time, sound)

    def layer(self, *sounds: Samples) -> Samples:
        """Mix sounds, padding shorter ones with silence."""
        return blip8.layer(*sounds)

    def effect(self, name: str, **options: object) -> Samples:
        """Return a ready-made game sound.

        Names: blip, select, back, coin, jump, powerup, laser, hurt,
        explosion, chime, kick, snare, hat, crash.
        """
        try:
            recipe = EFFECTS[name]
        except KeyError:
            names = ", ".join(EFFECTS)
            raise ValueError(f"Unknown effect {name!r}. Choose from: {names}.") from None
        return recipe(**options)

    def play(self, samples: Samples) -> None:
        """Play samples through the speakers and block until finished."""
        blip8.play(samples)

    def save(self, samples: Samples, path: str) -> None:
        """Write samples to a mono 16-bit .wav file."""
        blip8.save(samples, path)

    def plot(self, samples: Samples, **options: object) -> str:
        """Render samples as an ASCII waveform."""
        return blip8.plot(samples, **options)

    def show(self, samples: Samples, label: str = "", **options: object) -> None:
        """Print an ASCII waveform, with an optional heading."""
        blip8.show(samples, label=label, **options)

    def _volume(self, volume: float | None) -> float:
        return self.volume if volume is None else volume

    def _voice(
        self,
        voice: Voice | None,
        voice_options: dict[str, object],
    ) -> tuple[Voice, dict[str, object]]:
        if voice is None:
            voice_options.setdefault("duty", self.duty)
            return blip8.square, voice_options
        return voice, voice_options
