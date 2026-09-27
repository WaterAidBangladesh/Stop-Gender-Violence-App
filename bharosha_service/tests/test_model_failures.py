"""When the model returns nothing usable, the user must still get phone numbers.

gpt-oss-20b is a reasoning model: it writes a chain of thought into a separate
channel before answering, and when that consumes the completion budget the reply
comes back EMPTY or CUT OFF MID-SENTENCE, both with finish_reason "length".
Measured on this corpus at default settings: 7,400 characters of reasoning and
zero characters of content on one attempt; 551 characters of a 750-character
translation on another.

Both are now rejected. These tests force each failure and assert the request
still ends at a referral rather than at an error, a blank bubble, or — worst —
an answer built from an untranslated retrieval key.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import api  # noqa: E402
import chain  # noqa: E402
import referrals  # noqa: E402


def _http(host: str = "198.51.100.9"):
    """A stand-in for Starlette's Request.

    Each test uses its own address: the rate limiter is process-wide, and tests
    sharing one caller exhaust its burst and get throttled instead of exercising
    the path under test.
    """
    return SimpleNamespace(headers={}, client=SimpleNamespace(host=host))


# --- the guard itself ------------------------------------------------------

def test_empty_content_is_rejected() -> None:
    with pytest.raises(chain.Unavailable, match="empty"):
        chain.reject_if_unusable("", "length", "answer")
    with pytest.raises(chain.Unavailable, match="empty"):
        chain.reject_if_unusable("   ", "stop", "answer")


def test_truncated_content_is_rejected_even_though_it_looks_fine() -> None:
    """The dangerous case: plenty of text, cut off mid-sentence.

    A length check alone accepts this — it was accepting it — because 551
    characters of a 750-character translation looks like a translation.
    """
    partial = "সেফগার্ডিং মানে মানুষের স্বাস্থ্য, কল্যাণ এবং মানবাধিকার সুরক্ষা করা যাতে" * 3
    with pytest.raises(chain.Unavailable, match="truncated"):
        chain.reject_if_unusable(partial, "length", "translation")


def test_complete_content_passes() -> None:
    assert chain.reject_if_unusable(" an answer ", "stop", "answer") == "an answer"


# --- the path a user actually travels --------------------------------------

def test_failed_translation_sends_the_referral_not_a_bare_retrieval(monkeypatch) -> None:
    """A Bangla question whose translation fails must NOT fall through to
    retrieval on the untranslated text — the embedder is English-only, so that
    would match near-arbitrary passages and answer confidently from them."""
    calls = {"retrieve": 0}

    def exploding_translation(question: str) -> str:
        raise chain.Unavailable("translation: empty (finish_reason='length')")

    def counted_search(*args, **kwargs):
        calls["retrieve"] += 1
        return []

    monkeypatch.setattr(chain, "to_english", exploding_translation)
    monkeypatch.setattr(chain, "search", counted_search)
    monkeypatch.setattr(chain, "TRANSLATE_QUERIES", True)

    result = api.chat(
        api.ChatRequest(
            session_id="test-session-abcd", query="অর্থনৈতিক সহিংসতা কী?"
        ),
        _http(),
    )

    assert result["kind"] == "no_context"
    assert calls["retrieve"] == 0, "retrieval ran on an untranslated Bangla query"
    assert result["response"] == referrals.response_for("no_context", "bn")
    assert "999" in result["response"] and "109" in result["response"]


def test_failed_answer_sends_the_referral(monkeypatch) -> None:
    """Retrieval succeeded, the model then returned nothing usable."""

    def one_passage(query: str, language: str = "en", n_results: int = 4):
        return [
            chain.Passage(
                english="Safeguarding means protecting people from harm.",
                bangla=None,
                source="WaterAid",
                distance=0.2,
            )
        ]

    def exploding_answer(*args, **kwargs):
        raise chain.Unavailable("answer: truncated at 551 chars")

    monkeypatch.setattr(chain, "retrieve", one_passage)
    monkeypatch.setattr(chain, "answer", exploding_answer)

    result = api.chat(
        api.ChatRequest(
            session_id="test-session-efgh", query="What is safeguarding?"
        ),
        _http(),
    )

    assert result["kind"] == "no_context"
    assert "999" in result["response"]


def test_five_consecutive_failures_still_end_at_a_referral(monkeypatch) -> None:
    """Forced repeatedly, as asked: every attempt fails, every reply is useful."""

    def always_unusable(*args, **kwargs):
        raise chain.Unavailable("answer: empty (finish_reason='length')")

    monkeypatch.setattr(
        chain,
        "retrieve",
        lambda *a, **k: [
            chain.Passage(english="x", bangla=None, source="WaterAid", distance=0.1)
        ],
    )
    monkeypatch.setattr(chain, "answer", always_unusable)

    for i in range(5):
        result = api.chat(
            api.ChatRequest(
                session_id=f"test-session-{i:04d}", query="What is safeguarding?"
            ),
            # A different caller each time, so this measures the model-failure
            # path rather than the rate limiter.
            _http(host=f"203.0.113.{i + 20}"),
        )
        assert result["kind"] == "no_context"
        assert any(
            line.number in result["response"]
            for line in referrals.NATIONAL_HELPLINES
        ), f"attempt {i} produced a reply with no phone number in it"


def test_reasoning_effort_is_configured() -> None:
    """The setting that fixes the cause, not just the symptom.

    Default settings produced 1,768–2,048 completion tokens and intermittent
    empty or truncated replies; reasoning_effort="low" produced 102–164 tokens
    and complete output every time.
    """
    assert chain.REASONING_EFFORT == "low"
    assert chain.ANSWER_MAX_TOKENS >= 1000
