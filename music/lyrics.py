"""Words for a melody, in LilyPond's lyric syntax.

    Do -- na no -- bis pa -- cem

Syllables are separated by spaces. ' -- ' joins syllables of one word.
'_' leaves a note without a new syllable (the previous one is held over it,
a melisma). Tied notes never take a syllable. '__' (LilyPond's extender line)
is accepted and ignored here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .model import Melody, Note


@dataclass(frozen=True)
class Syllable:
    text: str
    syllabic: str  # "single", "begin", "middle", "end" (MusicXML's terms)


def parse_words(text: str) -> list[Syllable | None]:
    """Turn lyric text into syllables. None marks a held note ('_')."""
    tokens = [t for t in (text or "").split() if t != "__"]
    items: list[Syllable | None] = []
    hyphen_before = False
    for i, tok in enumerate(tokens):
        if tok == "--":
            continue
        if tok == "_":
            items.append(None)
            continue
        hyphen_after = i + 1 < len(tokens) and tokens[i + 1] == "--"
        if hyphen_before and hyphen_after:
            syllabic = "middle"
        elif hyphen_after:
            syllabic = "begin"
        elif hyphen_before:
            syllabic = "end"
        else:
            syllabic = "single"
        items.append(Syllable(tok, syllabic))
        hyphen_before = hyphen_after
    return items


def apply_words(melody: Melody, text: str) -> tuple[Melody, list[str]]:
    """Attach syllables to the melody's notes. Returns (new melody, warnings)."""
    items = parse_words(text)
    if not items:
        return melody, []
    events = []
    i = 0
    tied_from_prev = False
    for e in melody.events:
        if isinstance(e, Note):
            if not tied_from_prev and i < len(items):
                syl = items[i]
                i += 1
                e = replace(e, lyric=syl) if syl is not None else e
            tied_from_prev = e.tie_to_next
        else:
            tied_from_prev = False
        events.append(e)
    warnings = []
    leftover = sum(1 for x in items[i:] if x is not None)
    if leftover:
        warnings.append(f"{leftover} syllable(s) of the words didn't fit on the notes")
    return Melody(events, melody.barlines), warnings
