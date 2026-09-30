"""The referral blocks, and how a reply is assembled from model text plus one.

SAFETY DECIDES, THE AI SPEAKS. For every non-emergency category the model
writes the words and code appends a block from referrals.py. The block is the
whole of the safety content — the numbers and the one sentence of limit — so
it has to carry those on its own, and it must not carry the pleasantries the
model has just written in her own words.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import referrals  # noqa: E402
import safety  # noqa: E402

BLOCK_CATEGORIES = sorted(referrals.BLOCKS)


# --- the text -----------------------------------------------------------------


@pytest.mark.parametrize("category", BLOCK_CATEGORIES)
@pytest.mark.parametrize("language", ["en", "bn"])
def test_every_full_block_carries_a_real_number(category: str, language: str) -> None:
    text = referrals.referral_block(category, language, "full")
    numbers = [line.number for line in referrals.NATIONAL_HELPLINES] + [
        referrals.KAAN_PETE_ROI_NUMBER
    ]
    assert any(n in text for n in numbers), f"{category}/{language} full block has no number"


@pytest.mark.parametrize("category", BLOCK_CATEGORIES)
@pytest.mark.parametrize("language", ["en", "bn"])
def test_compact_is_one_line_and_shorter(category: str, language: str) -> None:
    full = referrals.referral_block(category, language, "full")
    compact = referrals.referral_block(category, language, "compact")
    assert "\n" not in compact.strip(), f"{category}/{language} compact block is not one line"
    # Low distress's full block is already one line, so "under half" is the
    # wrong bar for it; "never longer" is the invariant that holds for all.
    assert len(compact) <= len(full), f"{category}/{language} compact is longer than full"
    assert any(n in compact for n in ("109", "999", referrals.KAAN_PETE_ROI_NUMBER))


@pytest.mark.parametrize("category", BLOCK_CATEGORIES)
@pytest.mark.parametrize("language", ["en", "bn"])
def test_blocks_carry_no_opening_pleasantry(category: str, language: str) -> None:
    """The model has just written the opening, in her words, about her
    message. A block that begins "Thank you for telling me" would put the saved
    reply straight back under the live one."""
    text = referrals.referral_block(category, language, "full")
    openers = ("Thank you for telling me", "I'm sorry you", "আপনি বলেছেন, সেজন্য ধন্যবাদ")
    for opener in openers:
        assert not text.startswith(opener), f"{category}/{language} opens with a pleasantry"


def test_16263_is_in_no_block() -> None:
    """The health line stays out of everything that follows a disclosure."""
    for category, by_language in referrals.BLOCKS.items():
        for language, modes in by_language.items():
            for mode, text in modes.items():
                assert "16263" not in text, f"{category}/{language}/{mode}"


def test_every_model_answered_category_is_decided() -> None:
    """Block or explicitly no block — never silently nothing."""
    for category in safety._PRIORITY:
        if category in safety.DEVICE_CATEGORIES:
            continue
        assert category in referrals.BLOCKS or category in referrals.NO_BLOCK, category


def test_the_limit_sentence_survives_in_each_refusal_block() -> None:
    """The one thing a refusal must still say when the model wrote the rest."""
    limits = {
        "leave_decision": ("can't advise", "পরামর্শ দিতে পারি না"),
        "legal_advice": ("can't give legal advice", "আইনি পরামর্শ দিতে পারি না"),
        "medical_advice": ("can't tell you how to treat", "চিকিৎসা কীভাবে করবেন তা আমি বলতে পারি না"),
        "confront_or_evidence": ("won't suggest", "কোনো উপায় আমি বলব না"),
        "reporting_request": ("can't take a report", "অভিযোগ গ্রহণ করতে পারি না"),
        "coercive_control": ("can't advise you on what to do about the money", "পরামর্শ আমি দিতে পারি না"),
    }
    for category, (en, bn) in limits.items():
        assert en in referrals.referral_block(category, "en", "full"), category
        assert bn in referrals.referral_block(category, "bn", "full"), category


# --- the assembly ------------------------------------------------------------


def _fake_retrieval(monkeypatch, distance: float = 0.3) -> None:
    import chain

    passage = chain.Passage(english="x", bangla=None, source="WaterAid", distance=distance)
    monkeypatch.setattr(
        chain,
        "retrieve_scored",
        lambda *a, **k: chain.Retrieval(
            passages=[passage] if distance <= chain.RELEVANCE_FLOOR else [],
            candidates=[passage],
            nearest=distance,
        ),
    )


def _client_and_session(monkeypatch, session: str, distance: float = 0.3):
    import api
    import chain
    import sessions
    from fastapi.testclient import TestClient

    _fake_retrieval(monkeypatch, distance)
    monkeypatch.setattr(chain, "answer", lambda *a, **k: "MODEL WROTE THIS.")
    sessions.store.forget(session)
    client = TestClient(api.app)

    counter = {"n": 150}

    def ask(query: str) -> dict:
        counter["n"] += 1  # a distinct caller each time: measure assembly, not the limiter
        return client.post(
            "/chat",
            json={"session_id": session, "query": query},
            headers={"x-forwarded-for": f"203.0.113.{counter['n']}"},
        ).json()

    return ask


def test_a_recognised_category_gets_model_text_then_the_block(monkeypatch) -> None:
    """The first time the full block, every time after the one-liner — and the
    model's words always come first."""
    ask = _client_and_session(monkeypatch, "blocks-session-1")

    first = ask("my husband hits me")
    assert first["kind"] == "disclosure"
    full = referrals.referral_block("personal_disclosure", "en", "full")
    assert first["response"] == "MODEL WROTE THIS.\n\n" + full

    second = ask("my husband hits me every day")
    compact = referrals.referral_block("personal_disclosure", "en", "compact")
    assert second["response"] == "MODEL WROTE THIS.\n\n" + compact

    # A different category in the same session starts at full again.
    third = ask("should I leave him?")
    assert third["response"].endswith(referrals.referral_block("leave_decision", "en", "full"))


def test_social_and_identity_get_no_block(monkeypatch) -> None:
    ask = _client_and_session(monkeypatch, "blocks-session-2", distance=0.9)
    for query in ["hi", "thank you", "who are you?", "will my husband see this"]:
        assert ask(query)["response"] == "MODEL WROTE THIS.", query


def test_block_mode_is_per_session_and_per_category() -> None:
    import sessions

    store = sessions.SessionStore()
    assert store.block_mode("a", "leave_decision") == "full"
    assert store.block_mode("a", "leave_decision") == "compact"
    assert store.block_mode("a", "legal_advice") == "full"
    assert store.block_mode("b", "leave_decision") == "full"
    store.forget("a")
    assert store.block_mode("a", "leave_decision") == "full"


def test_the_whole_reply_goes_into_history(monkeypatch) -> None:
    """Model text AND block, so the model knows next turn what she has seen."""
    import sessions

    ask = _client_and_session(monkeypatch, "blocks-session-3")
    ask("he controls my money")
    ((question, answer),) = sessions.store.history("blocks-session-3")
    assert question == "he controls my money"
    assert answer.startswith("MODEL WROTE THIS.")
    assert referrals.referral_block("coercive_control", "en", "full") in answer


def test_a_bad_mode_is_refused() -> None:
    with pytest.raises(ValueError):
        referrals.referral_block("leave_decision", "en", "medium")
