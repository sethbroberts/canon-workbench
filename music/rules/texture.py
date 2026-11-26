"""The musical texture as the rules see it.

A canon's voices are turned into "sounds": one per sounding note, with tied
notes merged (a suspension is usually written as a tie, but it is one sound).
Rests separate sounds: a melodic step is only a step if nothing silent sits
between the two notes.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from fractions import Fraction

from music21 import meter

from ..canon import Voice
from ..model import Note, Pitch

STEP_INDEX = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}


@dataclass(frozen=True)
class Sound:
    voice: int  # 1-based voice number
    index: int  # position in that voice's list of sounds
    start: Fraction
    end: Fraction
    pitch: Pitch

    @property
    def midi(self) -> int:
        return self.pitch.midi

    @property
    def diatonic(self) -> int:
        """Staff position: counts letter names, so C4 -> D4 is 1 and C4 -> C5 is 7."""
        return self.pitch.octave * 7 + STEP_INDEX[self.pitch.step]


class Texture:
    def __init__(self, voices: list[Voice], time_signature: str = "4/4"):
        self.ts = meter.TimeSignature(time_signature)
        self.bar = Fraction(self.ts.barDuration.quarterLength).limit_denominator(64)
        self.sounds: dict[int, list[Sound]] = {}
        for v in voices:
            self.sounds[v.number] = _sounds_for(v)
        self.voice_numbers = [v.number for v in voices]
        self._starts = {n: [s.start for s in ss] for n, ss in self.sounds.items()}
        # Every point where any voice starts a note or a rest. Rests matter: a
        # rest between two fifths means they are not parallel.
        rest_starts = {t for v in voices for t in _rest_starts(v)}
        self.moments = sorted({s.start for ss in self.sounds.values() for s in ss} | rest_starts)
        self.end = max((ss[-1].end for ss in self.sounds.values() if ss), default=Fraction(0))

    # ---- looking things up ----

    def at(self, voice: int, t: Fraction) -> Sound | None:
        """The sound in `voice` at time t (None during a rest)."""
        starts = self._starts[voice]
        i = bisect.bisect_right(starts, t) - 1
        if i >= 0 and self.sounds[voice][i].end > t:
            return self.sounds[voice][i]
        return None

    def just_before(self, voice: int, t: Fraction) -> Sound | None:
        """The sound in `voice` that is sounding immediately before t."""
        starts = self._starts[voice]
        i = bisect.bisect_left(starts, t) - 1
        if i >= 0 and self.sounds[voice][i].end >= t:
            return self.sounds[voice][i]
        return None

    def prev(self, s: Sound) -> Sound | None:
        """The previous note in the same voice, if no rest separates them."""
        if s.index == 0:
            return None
        p = self.sounds[s.voice][s.index - 1]
        return p if p.end == s.start else None

    def next(self, s: Sound) -> Sound | None:
        """The next note in the same voice, if no rest separates them."""
        ss = self.sounds[s.voice]
        if s.index + 1 >= len(ss):
            return None
        n = ss[s.index + 1]
        return n if n.start == s.end else None

    def sounding(self, t: Fraction) -> list[Sound]:
        return [s for v in self.voice_numbers if (s := self.at(v, t)) is not None]

    def lowest_midi(self, t: Fraction) -> int | None:
        notes = self.sounding(t)
        return min((s.midi for s in notes), default=None)

    # ---- meter ----

    def weight(self, t: Fraction) -> float:
        """Metric weight: 1.0 on the downbeat, 0.5 on a secondary strong beat, less on weak beats."""
        pos = t % self.bar
        return float(self.ts.getAccentWeight(float(pos)))

    def bar_beat(self, t: Fraction) -> tuple[int, float]:
        """(bar number from 1, beat number from 1) in the meter's beat unit."""
        bar = int(t // self.bar) + 1
        beat_len = Fraction(self.ts.beatDuration.quarterLength).limit_denominator(64)
        beat = float((t % self.bar) / beat_len) + 1
        return bar, beat


def _rest_starts(voice: Voice) -> list[Fraction]:
    out, pos = [], Fraction(0)
    for e in voice.events:
        if not isinstance(e, Note):
            out.append(pos)
        pos += e.duration
    return out


def _sounds_for(voice: Voice) -> list[Sound]:
    sounds: list[Sound] = []
    pos = Fraction(0)
    tied = False
    for e in voice.events:
        if isinstance(e, Note):
            if tied and sounds:
                last = sounds[-1]
                sounds[-1] = Sound(last.voice, last.index, last.start, pos + e.duration, last.pitch)
            else:
                sounds.append(Sound(voice.number, len(sounds), pos, pos + e.duration, e.pitch))
            tied = e.tie_to_next
        else:
            tied = False
        pos += e.duration
    return sounds
