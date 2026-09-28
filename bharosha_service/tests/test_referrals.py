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


# --- the conversational tier ------------------------------------------------
#
# These assert restraint, which is the hard part to keep. Every one of them is a
# test that some text is ABSENT, because the failure they guard against is the
# one the app actually shipped with: answering "kemon acho?" with an apology, a
# five-item topic list and two emergency helplines. Nothing stops that text
# creeping back into a lighter reply except a test that fails when it does.

import safety  # noqa: E402

# Identity and privacy are excluded from the no-numbers rule below, and only
# from that one: "are you a real person" and "will he see this" are both
# questions about whether to trust this app with something, and both answers
# are more useful for saying where a human can be reached.
SOCIAL_CATEGORIES = tuple(
    c for c in safety.SOCIAL_CATEGORIES if c not in ("identity", "privacy")
)


@pytest.mark.parametrize("category", SOCIAL_CATEGORIES)
@pytest.mark.parametrize("language", ["en", "bn"])
def test_social_replies_carry_no_helpline_numbers(
    category: str, language: str
) -> None:
    """A hello is not a crisis, and answering it with 999 makes the app feel
    like it cannot tell the difference.

    The numbers are not lost: 999 and 109 sit on the chat screen as buttons the
    whole time. Identity is excluded — someone asking "are you a real person"
    is asking whether to talk to a human, and that one answer should say where.
    """
    text = referrals.response_for(category, language)
    for number in ("999", "109", "1098", referrals.KAAN_PETE_ROI_NUMBER):
        assert number not in text, f"{category}/{language} still lists {number}"


@pytest.mark.parametrize(
    "category", safety.SOCIAL_CATEGORIES + safety.VAGUE_CATEGORIES
)
@pytest.mark.parametrize("language", ["en", "bn"])
def test_light_replies_carry_no_topic_list(category: str, language: str) -> None:
    """No menu of five bullet points. A list is what the no-context reply is
    for; pasting it into every light reply is what made them all feel the same."""
    text = referrals.response_for(category, language)
    assert "\n- " not in text, f"{category}/{language} has a bullet list"
    assert text.count("\n\n") <= 3, f"{category}/{language} is too long"


@pytest.mark.parametrize("language", ["en", "bn"])
def test_vague_reply_asks_a_question_and_gives_exactly_one_number(
    language: str,
) -> None:
    """A bare "help" in THIS app may be someone who cannot yet type the
    sentence. So the reply asks for more AND leaves her with one number — one,
    because five reads as a diagnosis of what she is going through."""
    text = referrals.response_for("vague", language)
    assert "?" in text, "the vague reply must ask something"
    assert "999" in text
    for number in ("109", "1098", referrals.KAAN_PETE_ROI_NUMBER):
        assert number not in text


@pytest.mark.parametrize("language", ["en", "bn"])
def test_identity_reply_says_what_it_is_not(language: str) -> None:
    """Someone deciding whether to tell this app something is entitled to know
    what it is first. Saying "not a counsellor" is the point of the reply."""
    text = referrals.response_for("identity", language)
    denial = "not a person" if language == "en" else "মানুষ নই"
    assert denial in text.casefold()
    assert "109" in text, "it should still say where a human can be reached"


@pytest.mark.parametrize("language", ["en", "bn"])
def test_off_topic_reply_is_short_and_has_no_helplines(language: str) -> None:
    """The light end of the tiered fallback. "How do I cook rice" gets one line;
    a real question the corpus missed still gets the full no-context reply."""
    short = referrals.response_for("off_topic", language)
    full = referrals.response_for("no_context", language)
    assert len(short) < len(full) / 2
    assert "999" not in short and "109" not in short


@pytest.mark.parametrize("language", ["en", "bn"])
def test_third_party_reply_refers_without_advising_her_to_leave(
    language: str,
) -> None:
    """The refusal to advise on leaving applies whoever is asking. Told to a
    friend it is more dangerous, not less: she may act on it."""
    text = referrals.response_for("third_party_concern", language)
    assert "109" in text and "999" in text and "1098" in text
    urging = "pressing her to leave" if language == "en" else "চলে যাওয়ার জন্য চাপ"
    assert urging in text, "it must name pressing her to leave as a thing to avoid"


@pytest.mark.parametrize("language", ["en", "bn"])
def test_low_distress_names_kaan_pete_roi_with_its_hours(language: str) -> None:
    """Kaan Pete Roi runs 3pm–3am. A number that may not answer must never look
    like one that always does — the same rule as the suicide script."""
    text = referrals.response_for("low_distress", language)
    assert referrals.KAAN_PETE_ROI_NUMBER in text
    hours = (
        referrals.KAAN_PETE_ROI_HOURS_BN
        if language == "bn"
        else referrals.KAAN_PETE_ROI_HOURS_EN
    )
    assert hours in text


@pytest.mark.parametrize("language", ["en", "bn"])
def test_low_distress_neither_diagnoses_nor_interrogates(language: str) -> None:
    """Two failures this text must not have. "That sounds like depression" is a
    diagnosis it is not qualified to make; "what happened?" is the question that
    makes a person close the app."""
    text = referrals.response_for("low_distress", language).lower()
    for word in ("depress", "trauma", "disorder", "বিষণ্ণতা", "ট্রমা"):
        assert word not in text, f"low_distress/{language} diagnoses: {word}"
    if language == "en":
        assert "what happened" not in text
        assert "why" not in text.split("?")[0]


def test_the_numbers_are_still_marked_unverified() -> None:
    """A tripwire, not a check on the numbers.

    None of these has been dialled. 16430 sat in this app as the GBV helpline
    for months after it was replaced, because a document said so and nobody
    rang it. This fails the moment REFERRAL_VERIFICATION.md is marked done
    without the flag being flipped, and vice versa.
    """
    from pathlib import Path

    document = Path(__file__).resolve().parents[1] / "REFERRAL_VERIFICATION.md"
    assert document.exists(), "run tools/verification_list.py"

    if referrals.VERIFICATION_STATUS == "UNVERIFIED":
        return

    unticked = document.read_text(encoding="utf-8").count("- [ ]")
    assert unticked == 0, (
        f"VERIFICATION_STATUS says {referrals.VERIFICATION_STATUS!r} but "
        f"{unticked} claims in REFERRAL_VERIFICATION.md are still unticked"
    )


def test_every_claim_the_verification_list_makes_is_one_the_app_makes() -> None:
    """The list someone dials from must cover every number the app can give."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import verification_list

    listed = set(verification_list.CLAIMS)
    shipped = {line.number for line in referrals.NATIONAL_HELPLINES}
    assert shipped <= listed, f"no verification claims for {shipped - listed}"
