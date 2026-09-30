"""A web address is a contact. Found by the first live run of feel_review.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import assertions  # noqa: E402
import chain  # noqa: E402


@pytest.mark.parametrize(
    "reply",
    [
        # The actual leak, verbatim. Grounded on staff-facing material, in
        # Bangla, pointing a woman in Bangladesh at a UK reporting website.
        "ওয়াটারএইডের সেফকল (www.safecall.co.uk/wateraid) সেবায় আপনি আপনার পরিচয় গোপন রেখে অভিযোগ জমা দিতে পারেন।",
        "See https://www.wateraid.org/bd for how to report.",
        "Write to the safeguarding team at wateraid.org.",
        "The form is on safecall.co.uk.",
    ],
)
def test_a_web_address_is_caught_like_a_number(reply: str) -> None:
    assert assertions.contains_contact(reply) is not None
    assert assertions.check(reply, advisory=False) is not None


@pytest.mark.parametrize(
    "reply",
    [
        "That sounds exhausting, and it isn't your fault.",
        "I'm here for anything about safeguarding and gender-based violence.",
        "উপরের কল বাটন দিয়ে এখনই কারো সাথে কথা বলতে পারেন।",
        "She said he has done this for years. Would you like to say more?",
    ],
)
def test_ordinary_sentences_still_pass(reply: str) -> None:
    assert assertions.check(reply, advisory=True) is None


@pytest.mark.parametrize(
    "reply",
    [
        "বিশ্বাস করেন এমন কারো সঙ্গে কথা বলুন।",
        "নিচের হেল্পলাইনের সঙ্গে যোগাযোগ করুন।",
        "থানায় গিয়ে অভিযোগ জমা দিন।",
    ],
)
def test_bangla_imperatives_are_advice(reply: str) -> None:
    assert assertions.gives_advice(reply) is not None


def test_the_reporting_note_forbids_naming_a_channel() -> None:
    """The block is the only place a route may be named. Material written for
    WaterAid staff — Safecall, the incident form — is not written for her."""
    note = chain.APP_NOTES["reporting_request"]
    assert "Do NOT describe any reporting channel" in note
    assert "website" in note
