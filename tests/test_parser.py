from fractions import Fraction

import pytest

from music.model import Note, Pitch, Rest
from music.parser import ParseError, check_barlines, parse_melody


def test_basic_pitches_and_durations():
    m = parse_melody("C4/4 D4/8 E4 F#4/2")
    assert [e.pitch.name for e in m.events] == ["C4", "D4", "E4", "F#4"]
    assert [e.duration for e in m.events] == [1, Fraction(1, 2), Fraction(1, 2), 2]


def test_default_duration_is_quarter():
    m = parse_melody("C4 D4")
    assert all(e.duration == 1 for e in m.events)


def test_flats_double_accidentals_and_lowercase():
    m = parse_melody("Bb3 bb3 F##4 Ebb5 c4")
    names = [e.pitch.name for e in m.events]
    assert names == ["Bb3", "Bb3", "F##4", "Ebb5", "C4"]
    assert m.events[0].pitch.midi == 58


def test_middle_c_midi():
    assert Pitch("C", 0, 4).midi == 60


def test_dots():
    m = parse_melody("C4/4. D4/8 E4/2..")
    assert [e.duration for e in m.events] == [Fraction(3, 2), Fraction(1, 2), Fraction(7, 2)]


def test_rests():
    m = parse_melody("R/2 C4/4 r")
    assert isinstance(m.events[0], Rest) and m.events[0].duration == 2
    assert isinstance(m.events[2], Rest) and m.events[2].duration == 1


def test_tie_leading_tilde():
    m = parse_melody("A4/8 ~A4/2")
    assert m.events[0].tie_to_next is True
    assert m.events[1].tie_to_next is False


def test_tie_trailing_tilde():
    m = parse_melody("A4/8~ A4/2")
    assert m.events[0].tie_to_next is True


def test_tie_different_pitch_is_error():
    with pytest.raises(ParseError) as err:
        parse_melody("A4 ~B4")
    assert "different pitches" in str(err.value)


def test_tie_enharmonic_is_allowed():
    m = parse_melody("G#4 ~Ab4")
    assert m.events[0].tie_to_next


def test_barlines_and_comments():
    m = parse_melody("C4 D4 E4 F4 | G4/1 % a comment\n| C5/1")
    assert m.barlines == [4, 8]
    assert len(m) == 6
    assert m.duration == 12


def test_barline_check():
    m = parse_melody("C4 D4 E4 | F4")
    warnings = check_barlines(m, Fraction(4))
    assert len(warnings) == 1


def test_barline_touching_tokens():
    m = parse_melody("C4/1|D4/1")
    assert m.barlines == [4]


def test_all_errors_reported_at_once():
    with pytest.raises(ParseError) as err:
        parse_melody("C4 H4 D/4 E4/3")
    issues = err.value.issues
    assert [i.index for i in issues] == [2, 3, 4]
    assert "unknown pitch letter" in issues[0].message
    assert "missing octave" in issues[1].message
    assert "/3" in issues[2].message


def test_error_line_numbers():
    with pytest.raises(ParseError) as err:
        parse_melody("C4 D4\nE4 X9")
    assert err.value.issues[0].line == 2


def test_empty_text():
    assert len(parse_melody("   ")) == 0
