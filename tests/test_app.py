import pytest

import app as app_module
from app import app, slugify
from music.export import lilypond_executable

TUNE = "C4 D4 E4 C4 | E4 F4 G4/2"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "PIECES_DIR", tmp_path / "pieces")
    return app.test_client()


def piece(**kw):
    base = {"title": "Morning Round", "composer": "Seth", "melody": TUNE, "words": "one two three four five six seven",
            "voices": 2, "delay_bars": 1, "delay_beats": 0, "interval": "P1", "repeats": 1,
            "ending": "stagger", "time_signature": "4/4", "key": "C", "tempo": 90, "intentional": ["x|1.0|1-2"]}
    base.update(kw)
    return base


def test_slugify():
    assert slugify("Dona nobis pacem!") == "dona-nobis-pacem"
    assert slugify("Frère Jacques") == "frere-jacques"
    assert slugify("../../etc") == "etc"


def test_save_list_load_delete(client):
    r = client.post("/api/pieces", json=piece())
    assert r.get_json()["slug"] == "morning-round" and r.get_json()["replaced"] is False
    assert client.post("/api/pieces", json=piece()).get_json()["replaced"] is True
    listed = client.get("/api/pieces").get_json()
    assert [p["slug"] for p in listed] == ["morning-round"]
    loaded = client.get("/api/pieces/morning-round").get_json()
    assert loaded["melody"] == TUNE and loaded["intentional"] == ["x|1.0|1-2"] and loaded["tempo"] == 90
    client.delete("/api/pieces/morning-round")
    assert client.get("/api/pieces").get_json() == []


def test_save_needs_title(client):
    assert client.post("/api/pieces", json=piece(title="  ")).status_code == 400


def test_bad_slug_rejected(client):
    assert client.get("/api/pieces/..%2Fapp").status_code in (400, 404)
    assert client.get("/api/pieces/Bad_Name").status_code == 400


def test_render_includes_words_on_score(client):
    data = client.post("/api/render", json=piece()).get_json()
    assert data["ok"]
    assert ">one<" in "".join(data["svg"])


def test_render_warns_about_extra_syllables(client):
    data = client.post("/api/render", json=piece(words="a b c d e f g h i j")).get_json()
    assert any("didn't fit" in w for w in data["warnings"])


@pytest.mark.parametrize("kind,start", [("musicxml", b"<?xml"), ("midi", b"MThd"),
                                        ("ly-round", b"\\version"), ("ly-score", b"\\version")])
def test_exports(client, kind, start):
    r = client.post(f"/api/export/{kind}", json=piece())
    assert r.status_code == 200 and r.data.startswith(start)
    assert "morning-round" in r.headers["Content-Disposition"]


@pytest.mark.skipif(lilypond_executable() is None, reason="LilyPond not installed")
def test_pdf_export(client):
    r = client.post("/api/export/pdf-round", json=piece())
    assert r.status_code == 200 and r.data[:5] == b"%PDF-"
    assert 'filename="morning-round-round.pdf"' in r.headers["Content-Disposition"]


def test_export_with_bad_melody(client):
    r = client.post("/api/export/midi", json=piece(melody="C4 H9"))
    assert r.status_code == 400


def test_unknown_export(client):
    assert client.post("/api/export/wav", json=piece()).status_code == 404
