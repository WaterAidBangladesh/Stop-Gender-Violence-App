"""Conversation memory: the cap, the emergency note, and what history holds."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import chain  # noqa: E402
import referrals  # noqa: E402
import sessions  # noqa: E402


def test_twelve_turns_are_kept() -> None:
    assert sessions.MAX_TURNS == 12
    store = sessions.SessionStore()
    for i in range(20):
        store.record("s", f"q{i}", f"a{i}")
    kept = store.history("s")
    assert len(kept) == 12
    assert kept[0] == ("q8", "a8") and kept[-1] == ("q19", "a19")


def test_an_emergency_note_holds_the_category_and_nothing_she_typed() -> None:
    store = sessions.SessionStore()
    store.note("s", "immediate_danger")
    ((line, answer),) = store.history("s")
    assert answer == ""
    assert "immediate_danger" in line
    assert "emergency contacts were shown" in line
    assert line.startswith("[") and line.endswith("]")


def test_the_note_endpoint_accepts_only_emergency_categories() -> None:
    """The one door through which a client can write into a history. It
    accepts a category name from a fixed list and nothing else — so it cannot
    be used to plant text, and it cannot be used for a category the server
    would have answered itself."""
    import api
    from fastapi.testclient import TestClient

    client = TestClient(api.app)
    sessions.store.forget("note-session")

    ok = client.post("/chat/note", json={"session_id": "note-session", "category": "suicide_risk"}).json()
    assert ok == {"noted": True}
    assert len(sessions.store.history("note-session")) == 1

    for bad in ["greeting", "personal_disclosure", "she said she was scared", "x" * 40]:
        refused = client.post("/chat/note", json={"session_id": "note-session", "category": bad}).json()
        assert refused == {"noted": False}, bad
    assert len(sessions.store.history("note-session")) == 1, "a refused note was recorded"


def test_a_note_renders_as_one_line_in_the_prompt_history() -> None:
    """The model reads it as an event, not as something it once said."""
    history = [("hi", "Hello!"), ("[She sent a message the app treated as threat_to_life. The emergency contacts were shown to her.]", "")]
    rendered = "\n".join(f"user: {q}\nbharosha: {a}" if a else q for q, a in history)
    assert "bharosha: \n" not in rendered
    assert rendered.endswith("The emergency contacts were shown to her.]")
    assert rendered.count("\n") == 2


def test_privacy_text_says_a_label_may_be_sent() -> None:
    """The phone now sends a category name after an emergency. The privacy
    reply is a set of factual claims about this app, and one of them changed."""
    assert "topic label" in referrals.response_for("privacy", "en")
    assert "বিষয়ের নাম" in referrals.response_for("privacy", "bn")
    assert "topic label" in chain.APP_NOTES["privacy"]
