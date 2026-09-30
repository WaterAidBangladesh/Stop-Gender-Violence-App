"""The output check: what it catches, what it must let through, and the retry.

Do not trust the model — check. But a check that punishes kindness is the old
problem wearing a new badge, so half of these tests are about sentences the
check must NOT fire on.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import assertions  # noqa: E402
import chain  # noqa: E402
import referrals  # noqa: E402


# --- what it catches ------------------------------------------------------------


def test_the_leak_that_prompted_this_is_caught() -> None:
    """The actual reply that failed, kept verbatim as the regression case."""
    leaked = (
        "I’m here to help you think about what to do next. If someone is "
        "hurting you or you feel unsafe, it can be useful to:\n\n"
        "1. **Tell a trusted adult** – they can support you.\n"
        "2. **Direct them to a local safeguarding officer.**"
    )
    assert assertions.gives_advice(leaked) is not None
    assert assertions.check(leaked, advisory=True) is not None


@pytest.mark.parametrize(
    "reply",
    [
        "You should talk to a trusted friend first.",
        "Here's what you can do: reach out to a counsellor.",
        "- Encourage her to speak with someone she trusts",
        "আপনার উচিত একজন বিশ্বাসযোগ্য মানুষের সঙ্গে কথা বলা।",
        "প্রথমে, আপনি একটি নিরাপদ জায়গায় যান।",
    ],
)
def test_clearly_advisory_shapes_are_caught(reply: str) -> None:
    assert assertions.gives_advice(reply) is not None


@pytest.mark.parametrize(
    "reply, found",
    [
        ("You can call 109 any time.", "109"),
        ("Ring 999 now.", "999"),
        ("Kaan Pete Roi is on 09612-119911.", "09612"),
        ("Write to safeguardwab@wateraid.org.", "@"),
        ("৯৯৯ নম্বরে কল করুন।", "৯৯৯"),
        ("Their line is 16263, I think.", "16263"),
    ],
)
def test_a_number_or_email_the_model_wrote_is_always_caught(reply: str, found: str) -> None:
    """No exceptions — not even when grounded, not even when the number is
    right. The numbers arrive from referrals.py or not at all."""
    assert assertions.contains_contact(reply) == found
    assert assertions.check(reply, advisory=False) is not None
    assert assertions.check(reply, advisory=True) is not None


# --- what it must let through -------------------------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        "Sure, go ahead!",
        "I only cover safeguarding and gender-based violence.",
        "Could you tell me a bit more about what's happening?",
        "You're welcome!",
        "হ্যাঁ, অবশ্যই! কী জানতে চান?",
        "হুম, কী ভাবছেন?",
        # The gentle sentences the first version of this check wrongly ate.
        "It is important to me that you know this isn't your fault.",
        "First, I just want to say I'm glad you wrote.",
        "Next time you feel like this, you can come back here.",
        "আপনি চাইলে এখানে আরও কিছু বলতে পারেন, আমি শুনছি।",
        "আমাকে জানানো খুব গুরুত্বপূর্ণ ছিল — ধন্যবাদ।",
        # Two-digit numbers and years are not contacts.
        "You said he has done this for 10 years.",
        "She is only 14.",
    ],
)
def test_ordinary_and_gentle_replies_pass(reply: str) -> None:
    assert assertions.check(reply, advisory=True) is None, reply


def test_the_removed_patterns_are_gone() -> None:
    """Each of these caught kindness, not advice."""
    for gone in (
        r"\b(first|firstly|secondly|next|then|finally)\s*,",
        r"\bit\s+is\s+important\s+to\b",
        r"আপনি\s*(করতে|করা)\s*পারেন",
        r"(করা|জানানো|যোগাযোগ\s*করা)\s*(খুব\s*)?(জরুরি|গুরুত্বপূর্ণ)",
    ):
        assert gone not in assertions._ADVISORY


def test_grounded_answers_with_no_category_may_carry_steps() -> None:
    """WaterAid's material is full of legitimate numbered steps and the model
    is licensed to relay them. The advice check is off there; only the
    contact check applies."""
    steps = "The material lists three steps:\n1. Listen.\n2. Believe her.\n3. Refer."
    assert assertions.check(steps, advisory=False) is None
    assert assertions.check(steps, advisory=True) is not None


# --- the retry ----------------------------------------------------------------


def _pipeline(monkeypatch, replies: list[str], session: str, query: str = "hello"):
    """Fake retrieval below the floor and a model that returns `replies` in
    turn. Returns the body and the retry notes the model was given."""
    import api
    from fastapi.testclient import TestClient

    passage = chain.Passage(english="x", bangla=None, source="WaterAid", distance=0.8)
    monkeypatch.setattr(
        chain, "retrieve_scored",
        lambda *a, **k: chain.Retrieval(passages=[], candidates=[passage], nearest=0.8),
    )
    notes: list[str] = []
    queue = list(replies)

    def fake_answer(*_a, retry_note: str = "", **_k):
        notes.append(retry_note)
        return queue.pop(0)

    monkeypatch.setattr(chain, "answer", fake_answer)
    import sessions
    sessions.store.forget(session)
    body = TestClient(api.app).post(
        "/chat",
        json={"session_id": session, "query": query},
        headers={"x-forwarded-for": f"203.0.113.{hash(session) % 200 + 20}"},
    ).json()
    return body, notes


def test_a_bad_first_draft_is_retried_once_with_the_note(monkeypatch) -> None:
    before = assertions.counter.snapshot()
    body, notes = _pipeline(
        monkeypatch,
        ["You should tell a trusted adult first.", "I'm glad you wrote. What's on your mind?"],
        "retry-session-1",
    )
    assert body["response"] == "I'm glad you wrote. What's on your mind?"
    assert notes == ["", chain.RETRY_NOTE]
    after = assertions.counter.snapshot()
    assert after["output_retries"] == before["output_retries"] + 1
    assert after["output_fallbacks"] == before["output_fallbacks"]


def test_a_bad_retry_falls_back_to_the_fixed_text(monkeypatch) -> None:
    before = assertions.counter.snapshot()
    body, notes = _pipeline(
        monkeypatch,
        ["You should tell a trusted adult.", "You must call 109 now."],
        "retry-session-2",
    )
    assert body["response"] == referrals.response_for("greeting", "en")
    assert len(notes) == 2, "exactly one retry, never more"
    after = assertions.counter.snapshot()
    assert after["output_retries"] == before["output_retries"] + 1
    assert after["output_fallbacks"] == before["output_fallbacks"] + 1


def test_a_clean_first_draft_is_not_retried(monkeypatch) -> None:
    before = assertions.counter.snapshot()
    body, notes = _pipeline(monkeypatch, ["Hello! What would you like to talk about?"], "retry-session-3")
    assert body["response"] == "Hello! What would you like to talk about?"
    assert notes == [""]
    after = assertions.counter.snapshot()
    assert after["output_checks"] == before["output_checks"] + 1
    assert after["output_retries"] == before["output_retries"]


def test_a_number_in_a_categorised_reply_is_retried_then_replaced(monkeypatch) -> None:
    """The model wrote a number under a disclosure. First retry; if it does it
    again, the fixed text — which carries the right number from referrals.py."""
    body, notes = _pipeline(
        monkeypatch,
        ["That's awful. Call 109.", "That's awful. Call 999."],
        "retry-session-4",
        query="my husband hits me",
    )
    assert body["response"] == referrals.response_for("personal_disclosure", "en")
    assert len(notes) == 2


def test_health_reports_retries_and_fallbacks_separately() -> None:
    snap = assertions.counter.snapshot()
    for key in ("output_checks", "output_retries", "output_fallbacks", "retry_rate", "fallback_rate"):
        assert key in snap
    assert "discarded" not in " ".join(snap)
