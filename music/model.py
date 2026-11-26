"""Core data types: pitches, notes, rests, melodies.

Durations are stored as Fractions of a quarter note ("quarter lengths"),
the same unit music21 uses:  whole = 4, half = 2, quarter = 1, eighth = 1/2.
Fractions keep triplets and dotted values exact (no floating-point drift).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Union

# Semitones above C for each natural note name.
STEP_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


@dataclass(frozen=True)
class Pitch:
    """A spelled pitch, e.g. Pitch("F", 1, 4) is F#4."""

    step: str  # "C" .. "B"
    alter: int  # -2 (double flat) .. +2 (double sharp)
    octave: int  # scientific octave: middle C is C4

    @property
    def midi(self) -> int:
        """MIDI note number (middle C = 60)."""
        return 12 * (self.octave + 1) + STEP_SEMITONES[self.step] + self.alter

    @property
    def name(self) -> str:
        """Name in this app's text syntax, e.g. 'Bb4' or 'F#3'."""
        accidental = "#" * self.alter if self.alter > 0 else "b" * -self.alter
        return f"{self.step}{accidental}{self.octave}"

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Note:
    pitch: Pitch
    duration: Fraction
    tie_to_next: bool = False  # True if this note is tied into the following note

    @property
    def is_rest(self) -> bool:
        return False


@dataclass(frozen=True)
class Rest:
    duration: Fraction

    @property
    def is_rest(self) -> bool:
        return True


Event = Union[Note, Rest]


@dataclass
class Melody:
    """An ordered list of notes and rests.

    barlines holds the positions (in quarter lengths from the start) where
    the user typed '|'. They are optional and only used to check the meter.
    """

    events: list[Event] = field(default_factory=list)
    barlines: list[Fraction] = field(default_factory=list)

    @property
    def duration(self) -> Fraction:
        return sum((e.duration for e in self.events), Fraction(0))

    def notes(self) -> list[Note]:
        return [e for e in self.events if isinstance(e, Note)]

    def __len__(self) -> int:
        return len(self.events)
