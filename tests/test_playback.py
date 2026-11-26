from fractions import Fraction

from app import app
from music.canon import CanonSettings, build_canon
from music.parser import parse_melody
from music.playback import playback_data
from music.render import build_score, render_score, to_musicxml


def test_ties_merge_into_one_event_and_rests_are_silent():
    voices = build_canon(parse_melody("C4/4 D4/2 ~D4/4 R/4 E4/8"), CanonSettings(voices=1))
    events = playback_data(voices)["voices"][0]["events"]
    assert events == [
        {"midi": 60, "start": 0.0, "dur": 1.0},
        {"midi": 62, "start": 1.0, "dur": 3.0},
        {"midi": 64, "start": 5.0, "dur": 0.5},
    ]


def test_four_voice_round_events():
    m = parse_melody("C4 D4 E4 C4")
    data = playback_data(build_canon(m, CanonSettings(voices=4, delay=Fraction(2))))
    assert data["length"] == 10  # last voice enters at 6, sings 4 beats
    starts = [v["events"][0]["start"] for v in data["voices"]]
    assert starts == [0, 2, 4, 6]
    assert all(len(v["events"]) == 4 for v in data["voices"])


def test_timemap_ids_exist_in_svg():
    voices = build_canon(parse_melody("C4 D4 E4 F4"), CanonSettings(voices=2, delay=Fraction(2)))
    result = render_score(to_musicxml(build_score(voices)))
    svg = "".join(result["pages"])
    ids = {i for moment in result["timemap"] for i in moment["on"]}
    assert len(ids) == 8
    assert all(f'id="{i}"' in svg for i in ids)
    assert result["timemap"][0]["q"] == 0


def test_api_returns_playback_and_timemap():
    client = app.test_client()
    r = client.post("/api/render", json={"melody": "C4 D4 E4 F4", "voices": 3, "delay_bars": 0, "delay_beats": 2})
    data = r.get_json()
    assert data["ok"]
    assert len(data["playback"]["voices"]) == 3
    assert data["timemap"]
