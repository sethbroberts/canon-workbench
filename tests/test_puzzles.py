from fractions import Fraction

import pytest

import app as app_module
from app import app
from music import puzzles

ALL = puzzles.load_all()


def test_there_are_starter_puzzles_of_every_kind():
    assert len(ALL) >= 6
    assert {p["type"] for p in ALL} == {"complete", "entries", "fix"}


@pytest.mark.parametrize("p", ALL, ids=[p["id"] for p in ALL])
def test_puzzle_is_valid(p):
    assert puzzles.verify(p) == []
    assert p["hints"] and p["intro"] and p["title"]


def test_public_view_hides_answers():
    for p in ALL:
        view = puzzles.public(p)
        assert "solution" not in view and "answers" not in view


def test_complete_accepts_other_good_answers_and_rejects_bad_ones():
    p = puzzles.find("01-frere-jacques-ending")
    assert puzzles.grade(p, {"text": "F4/1 | F4/1"})["solved"]
    bad = puzzles.grade(p, {"text": "G4/1 | G4/1"})
    assert not bad["solved"] and "error" in bad["message"]
    short = puzzles.grade(p, {"text": "F4/1"})
    assert not short["solved"] and "1 bars long" in short["message"]


def test_entries_wrong_answer_explains():
    p = puzzles.find("07-canon-at-the-fifth-entries")
    r = puzzles.grade(p, {"delay_beats": 4, "interval": "P1"})
    assert not r["solved"] and "error" in r["message"]
    assert puzzles.grade(p, {"delay_beats": 4, "interval": "P5"})["solved"]


def test_fix_needs_a_change_and_same_length():
    p = puzzles.find("04-evening-round-fix")
    assert "Nothing has changed" in puzzles.grade(p, {"text": p["melody"]})["message"]
    assert "same length" in puzzles.grade(p, {"text": p["melody"] + " F4/1"})["message"]


def test_bad_notes_are_reported_not_crashed():
    p = puzzles.find("04-evening-round-fix")
    assert "couldn't be read" in puzzles.grade(p, {"text": "H4 Q2"})["message"]


# ---- the web API ----

def test_api_lists_and_opens_without_answers():
    c = app.test_client()
    listed = c.get("/api/puzzles").get_json()
    assert [p["id"] for p in listed] == [p["id"] for p in ALL]
    one = c.get("/api/puzzles/03-evening-round-entries").get_json()
    assert "answers" not in one and one["melody"]


def test_api_check_and_reveal():
    c = app.test_client()
    r = c.post("/api/puzzles/03-evening-round-entries/check", json={"delay_beats": 8, "interval": "P1"}).get_json()
    assert r["solved"]
    sol = c.get("/api/puzzles/05-evening-round-third-phrase/solution").get_json()
    assert sol["solution"].startswith("F4")
    assert c.get("/api/puzzles/nope").status_code == 404


def test_api_round_guide_feedback():
    phrases = ["A4/2 G4/2 | F4/1", "C5/4 Bb4/4 C5/2 | C5/4 Bb4/4 A4/2", "F4/1 | G4/1"]
    data = {"melody": "\n".join(phrases), "voices": 3, "delay_bars": 2, "key": "F",
            "guide": {"mode": "round", "phrase_bars": 2, "progression": "I V I I", "parts": phrases}}
    r = app.test_client().post("/api/render", json=data).get_json()
    assert r["ok"] and all(p["ok"] for p in r["guide"]["parts"])
    # Phrase 3's G4 lands on a downbeat under I (F A C): not a chord tone.
    assert [(c["phrase"], c["note"], c["chord"]) for c in r["guide"]["chord_fit"]] == [(3, "G4", "I")]
    assert r["playback"]["backing"] and r["playback"]["backing"][0]["midi"]


def test_api_bad_progression_is_reported():
    data = {"melody": "C4/1", "voices": 1, "delay_bars": 1, "key": "C",
            "guide": {"mode": "round", "phrase_bars": 1, "progression": "I Q", "parts": ["C4/1"]}}
    r = app.test_client().post("/api/render", json=data).get_json()
    assert "unknown chord" in r["guide"]["progression_error"]
