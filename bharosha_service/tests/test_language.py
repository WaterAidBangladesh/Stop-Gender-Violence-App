"""Language detection and greeting mirroring.

Three languages now: Bangla script, Bangla in Latin letters, and English. The
first two get Bangla replies. A person who types "amar shami amake mare" reads
Bangla; she typed it in Latin letters because that is what her keyboard
offered, and answering her in English was the wrong call for as long as it
lasted.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import referrals  # noqa: E402
import safety  # noqa: E402


@pytest.mark.parametrize(
    "message, expected",
    [
        ("সেফগার্ডিং কী", "bn"),
        ("safeguarding মানে কী", "bn"),
        ("amar shami protidin amake gali dey", "bn_roman"),
        ("ki korbo?", "bn_roman"),
        ("amake marche help", "bn_roman"),
        ("kemon acho", "bn_roman"),
        ("tumi ki help korte parbe?", "bn_roman"),
        ("achha bujhlam", "bn_roman"),
        ("amar mon ta kharap", "bn_roman"),
        ("What is safeguarding?", "en"),
        ("he keeps my salary", "en"),
        ("I want to die", "en"),
        ("hmm", "en"),
        ("Assalamu alaikum", "en"),
        # One romanised word is not enough — English sentences contain these.
        ("ma please help", "en"),
        ("I have a problem with my phone", "en"),
        ("na I am fine", "en"),
    ],
)
def test_detect_language(message: str, expected: str) -> None:
    assert safety.detect_language(message) == expected


def test_the_word_list_contains_no_english() -> None:
    """Each of these, on its own, turned an English sentence into two hits."""
    for word in ("to", "help", "problem", "phone", "hmm", "the", "and", "is"):
        assert word not in safety.ROMANISED_BANGLA_WORDS, word


def test_romanised_bangla_reads_the_bangla_text() -> None:
    for category in ("greeting", "personal_disclosure", "vague", "low_distress"):
        assert referrals.response_for(category, "bn_roman") == referrals.response_for(category, "bn")
    assert referrals.referral_block("leave_decision", "bn_roman", "full") == referrals.referral_block(
        "leave_decision", "bn", "full"
    )
    assert referrals.text_language("bn_roman") == "bn"
    assert referrals.text_language("en") == "en"


@pytest.mark.parametrize(
    "message, category, must_contain_bn, must_contain_en",
    [
        ("Assalamu alaikum", "greeting_salam", "ওয়ালাইকুম আসসালাম", "Walaikum assalam"),
        ("salam", "greeting_salam", "ওয়ালাইকুম আসসালাম", "Walaikum assalam"),
        ("আসসালামু আলাইকুম", "greeting_salam", "ওয়ালাইকুম আসসালাম", "Walaikum assalam"),
        ("নমস্কার", "greeting_namaskar", "নমস্কার", "Namaskar"),
        ("namaskar", "greeting_namaskar", "নমস্কার", "Namaskar"),
        ("hi", "greeting", "হ্যালো", "Hello"),
        ("kemon acho?", "greeting", "হ্যালো", "Hello"),
    ],
)
def test_the_greeting_fallback_mirrors_hers(
    message: str, category: str, must_contain_bn: str, must_contain_en: str
) -> None:
    assert referrals.greeting_category(message) == category
    assert must_contain_bn in referrals.response_for(category, "bn")
    assert must_contain_en in referrals.response_for(category, "en")


def test_salam_is_not_answered_with_namaskar_anywhere() -> None:
    text = referrals.response_for("greeting_salam", "bn")
    assert "নমস্কার" not in text


def test_the_api_fallback_mirrors_the_greeting(monkeypatch) -> None:
    """With the model unreachable, "Assalamu alaikum" still gets the right
    reply — the fixed text must not undo what the prompt asks the model for."""
    import api
    import chain
    from fastapi.testclient import TestClient

    def unavailable(*_a, **_k):
        raise chain.Unavailable("no model")

    monkeypatch.setattr(chain, "retrieve_scored", unavailable)
    client = TestClient(api.app)

    for n, (message, expected) in enumerate([
        ("Assalamu alaikum", "Walaikum assalam"),
        ("নমস্কার", "নমস্কার"),
        ("hi", "Hello"),
        ("kemon acho", "হ্যালো"),  # romanised -> Bangla text
    ]):
        body = client.post(
            "/chat",
            json={"session_id": "x" * 10, "query": message},
            headers={"x-forwarded-for": f"203.0.113.{200 + n}"},
        ).json()
        assert expected in body["response"], message


def test_romanised_bangla_is_translated_for_retrieval(monkeypatch) -> None:
    """The English-only embedder can represent "amake marche" no better than
    Bangla script, so both go through the translation step for the search key."""
    import chain
    import embedding

    seen = {}
    monkeypatch.setattr(embedding, "is_multilingual", lambda: False)
    monkeypatch.setattr(chain, "TRANSLATE_QUERIES", True)
    monkeypatch.setattr(chain, "to_english", lambda q: seen.setdefault("q", q) or "translated")
    monkeypatch.setattr(chain, "search", lambda key, n_results: [])

    chain.retrieve_scored("amar shami amake mare", "bn_roman")
    assert seen == {"q": "amar shami amake mare"}
