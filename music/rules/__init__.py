"""The rule checker.

    findings = check_canon(voices, "4/4", key_text="F")

Each Finding has a rule label (e.g. "parallel_fifths"), a severity:
  error    breaks the style's rules
  warning  allowed but worth a second look
  info     a recognized, correctly handled dissonance (suspension, passing tone, ...)
and the notes involved, so the page can color them and play the passage.
The labels are stable: the v2 tutor will count them to see what needs practice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from ..canon import Voice
from .texture import Texture

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass(frozen=True)
class Profile:
    """A style: which dissonance figures it accepts, and the comfortable range."""

    name: str = "renaissance"
    range_low: int = 62  # D4
    range_high: int = 77  # F5
    figures: frozenset[str] = frozenset(
        {"passing tone", "neighbor tone", "anticipation", "cambiata", "échappée"}
    )


RENAISSANCE = Profile()


@dataclass
class Finding:
    rule: str
    severity: str
    message: str
    start: Fraction
    end: Fraction
    voices: tuple[int, ...]
    notes: list[tuple[int, Fraction]] = field(default_factory=list)  # (voice, note start)
    label: str = ""  # short name shown in lists, e.g. "7–6 suspension"

    @property
    def key(self) -> str:
        """Identifies the finding across re-checks (for 'mark as intentional')."""
        return f"{self.rule}|{float(self.start)}|{'-'.join(map(str, self.voices))}"

    def to_dict(self, tx: Texture) -> dict:
        bar, beat = tx.bar_beat(self.start)
        play_from = (self.start // tx.bar) * tx.bar
        last = max(self.end, self.start + Fraction(1, 64))
        play_to = min(tx.end, ((last - Fraction(1, 64)) // tx.bar + 1) * tx.bar)
        if play_to <= play_from:
            play_to = min(tx.end, play_from + tx.bar)
        return {
            "key": self.key,
            "rule": self.rule,
            "severity": self.severity,
            "label": self.label or self.rule.replace("_", " "),
            "message": self.message,
            "bar": bar,
            "beat": round(beat, 3),
            "voices": list(self.voices),
            "start": float(self.start),
            "notes": [[v, float(t)] for v, t in self.notes],
            "play_from": float(play_from),
            "play_to": float(play_to),
        }


def check_canon(
    voices: list[Voice],
    time_signature: str = "4/4",
    key_text: str = "",
    unison: bool = True,
    profile: Profile = RENAISSANCE,
    melody_length: Fraction | None = None,
) -> tuple[list[Finding], Texture]:
    """Run every rule.

    unison: all voices sing the same pitches (a round), so melodic and range
            rules only need checking once.
    melody_length: length of one pass of the melody, used to find its final note.
    """
    from . import dissonance, melodic, motion

    tx = Texture(voices, time_signature)
    findings: list[Finding] = []
    findings += dissonance.check(tx, profile)
    findings += motion.check(tx)
    findings += melodic.check(tx, profile, key_text, unison, melody_length)
    findings.sort(key=lambda f: (f.start, SEVERITY_ORDER[f.severity], f.voices))
    return findings, tx
