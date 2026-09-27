"""Tests for the hardcoded referral text.

These are content tests. They exist because this text is the whole product on
the paths that matter most — an emergency reply is not generated, retrieved or
translated at runtime, so what is written here is exactly what a frightened
person reads.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import referrals  # noqa: E402


@pytest.mark.parametrize("language", ["en", "bn"])
def test_suicide_response_puts_999_before_kaan_pete_roi(language: str) -> None:
    """999 is the only 24/7 option, so it must come first.

    Kaan Pete Roi runs 3pm–3am. Listing it first would put a number that may go
    unanswered above the one that never does.
    """
    text = referrals.response_for("suicide_risk", language)
    assert text.index("999") < text.index(referrals.KAAN_PETE_ROI_NUMBER)


@pytest.mark.parametrize(
    "language, hours",
    [("en", referrals.KAAN_PETE_ROI_HOURS_EN), ("bn", referrals.KAAN_PETE_ROI_HOURS_BN)],
)
def test_kaan_pete_roi_hours_are_in_the_text(language: str, hours: str) -> None:
    """Someone calling at 9am must learn the hours before they dial, not after.

    The hours belong in the response body, not only in a data field nobody
    renders.
    """
    text = referrals.response_for("suicide_risk", language)
    assert referrals.KAAN_PETE_ROI_NUMBER in text
    assert hours in text


@pytest.mark.parametrize("language", ["en", "bn"])
def test_no_context_offers_what_it_can_do(language: str) -> None:
    """The no-context reply is a primary experience, not an error.

    It must acknowledge the gap, say what Bharosha can help with, and hand over
    a referral — never read as a rejection or a dead end.
    """
    text = referrals.response_for("no_context", language)
    assert len(text) > 300, "too terse to read as anything but a refusal"
    assert "109" in text and "999" in text
    assert referrals.SAFEGUARDING_EMAIL in text
    # Names at least three of the subjects it does cover.
    subjects = ("safeguarding", "violence", "prevent") if language == "en" else (
        "সেফগার্ডিং",
        "সহিংসতা",
        "প্রতিরোধ",
    )
    assert all(subject in text for subject in subjects)


@pytest.mark.parametrize("language", ["en", "bn"])
def test_starting_and_rate_limited_still_give_numbers(language: str) -> None:
    """Degraded states must not be dead ends either."""
    for category in ("starting", "rate_limited"):
        text = referrals.response_for(category, language)
        assert "999" in text and "109" in text


def test_16263_is_labelled_a_health_line() -> None:
    """Confirmed by WaterAid: Shastho Batayon, not a GBV hotline."""
    line = referrals.helpline("16263")
    assert "health" in line.name_en.lower()
    assert "GBV" not in line.name_en and "Gender" not in line.name_en
    assert line.in_emergency_script is False


@pytest.mark.parametrize("language", ["en", "bn"])
def test_no_gbv_script_routes_to_the_health_line(language: str) -> None:
    for category in ("immediate_danger", "active_violence", "threat_to_life",
                     "suicide_risk", "child_disclosure", "no_context"):
        assert "16263" not in referrals.response_for(category, language)


def test_amic_stays_out_until_confirmed() -> None:
    """Left out on instruction: the contact could not be verified as current."""
    organisations = [f.organisation for f in referrals.SAFEGUARDING_FOCAL_POINTS]
    assert len(organisations) == 9
    assert not any("Addiction" in name or "AMIC" in name for name in organisations)


@pytest.mark.parametrize("language", ["en", "bn"])
def test_answer_footer_carries_the_numbers(language: str) -> None:
    """The model is forbidden from writing numbers, so the footer must have them."""
    footer = referrals.answer_footer(language)
    assert "109" in footer and "999" in footer
