from fractions import Fraction

import pytest
from music21 import converter, pitch

from music.canon import CanonSettings, build_canon
from music.export import (PieceInfo, instructions, lilypond_executable, lilypond_source, ly_pitch,
                          to_midi, to_pdf, with_metadata)
from music.lyrics import apply_words, parse_words
from music.parser import parse_melody
from music.render import build_score, to_musicxml

TUNE = "F4/4 G4 A4 F4 | A4 Bb4 C5/2 | C5/8 D5 C5 Bb4 A4/4 F4 | F4 C4 F4/2"
WORDS = "Do -- na no -- bis pa -- cem _ do -- mi -- ne, Do -- na no -- bis pa -- cem"


# ---- lyrics ----

def test_parse_words_syllabic():
    items = parse_words("Do -- na no -- bis pa -- cem _ Lord")
    assert [(s.text, s.syllabic) if s else None for s in items] == [
        ("Do", "begin"), ("na", "end"), ("no", "begin"), ("bis", "end"),
        ("pa", "begin"), ("cem", "end"), None, ("Lord", "single")]


def test_middle_syllable():
    assert [s.syllabic for s in parse_words("al -- le -- lu -- ia")] == ["begin", "middle", "middle", "end"]


def test_words_skip_rests_and_tied_notes():
    m, warnings = apply_words(parse_melody("C4 R/4 D4/2 ~D4/4 E4"), "one two three")
    lyrics = [e.lyric.text if getattr(e, "lyric", None) else None for e in m.events]
    assert lyrics == ["one", None, "two", None, "three"]
    assert warnings == []


def test_too_many_syllables_warns():
    _, warnings = apply_words(parse_melody("C4 D4"), "a b c d")
    assert warnings and "2 syllable" in warnings[0]


def test_lyrics_reach_every_voice_and_musicxml():
    m, _ = apply_words(parse_melody(TUNE), WORDS)
    voices = build_canon(m, CanonSettings(voices=2, delay=Fraction(4)))
    xml = to_musicxml(build_score(voices, "4/4", "F"))
    assert xml.count("<text>Do</text>") == 4  # twice per voice
    assert "<syllabic>begin</syllabic>" in xml


# ---- LilyPond ----

@pytest.mark.parametrize("name,expected", [
    ("C4", "c'"), ("C5", "c''"), ("C3", "c"), ("B2", "b,"), ("F#4", "fis'"),
    ("B-4", "bes'"), ("E-4", "es'"), ("A-3", "as"), ("E--4", "eses'"), ("C##4", "cisis'"),
])
def test_ly_pitch(name, expected):
    assert ly_pitch(pitch.Pitch(name)) == expected


def _round_source(**kw):
    m, _ = apply_words(parse_melody(TUNE), WORDS)
    settings = CanonSettings(voices=kw.get("voices", 4), delay=kw.get("delay", Fraction(4)),
                             interval=kw.get("interval", "P1"))
    return lilypond_source(m, settings, "4/4", "F", PieceInfo("Peace", "Seth", "For Ann"), kw.get("layout", "round"))


def test_round_layout_has_entry_marks_words_and_header():
    src = _round_source()
    assert src.count("\\circle") == 4
    assert 'title = "Peace"' in src and 'dedication = "For Ann"' in src
    assert '"Do" --' in src and "\\lyricsto" in src
    assert "\\key f \\major" in src
    assert "A round for four voices" in src


def test_canon_at_fifth_instructions():
    text = instructions(CanonSettings(voices=2, delay=Fraction(4), interval="P5"), Fraction(16), Fraction(4))
    assert "fifth above" in text


def test_full_score_layout_has_a_staff_per_voice():
    src = _round_source(layout="score", voices=3)
    assert src.count("\\new Staff") == 3
    assert src.count("\\lyricsto") == 3


def test_quotes_in_words_are_escaped():
    m, _ = apply_words(parse_melody("C4 D4"), 'say "hi"')
    src = lilypond_source(m, CanonSettings(voices=1), "4/4", "C", PieceInfo('A "quoted" title'), "round")
    assert '\\"hi\\"' in src and 'A \\"quoted\\" title' in src


needs_lilypond = pytest.mark.skipif(lilypond_executable() is None, reason="LilyPond not installed")


@needs_lilypond
@pytest.mark.parametrize("layout", ["round", "score"])
def test_pdf(layout):
    pdf = to_pdf(_round_source(layout=layout))
    assert pdf[:5] == b"%PDF-"


@needs_lilypond
def test_awkward_rhythms_engrave():
    # Notes crossing barlines, dotted values, rests, ties, sharps and flats.
    m = parse_melody("C4/2. D4/2 E4/4. F#4/8 Bb4/1 ~Bb4/4 R/4 G4/2 | C5/1")
    src = lilypond_source(m, CanonSettings(voices=3, delay=Fraction(3)), "3/4", "Bb", PieceInfo("Odd"), "score")
    assert to_pdf(src)[:5] == b"%PDF-"


# ---- MIDI and MusicXML ----

def test_midi_round_trips():
    voices = build_canon(parse_melody(TUNE), CanonSettings(voices=3, delay=Fraction(4)))
    data = to_midi(build_score(voices, "4/4", "F"), bpm=80)
    assert data[:4] == b"MThd"
    back = converter.parse(data, format="midi")
    assert len(back.parts) == 3


def test_musicxml_has_title():
    voices = build_canon(parse_melody(TUNE), CanonSettings(voices=2, delay=Fraction(4)))
    score = with_metadata(build_score(voices, "4/4", "F"), PieceInfo("Peace", "Seth"))
    xml = to_musicxml(score)
    assert "Peace" in xml and "Seth" in xml
