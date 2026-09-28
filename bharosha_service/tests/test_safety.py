"""Tests for the deterministic safety layer.

This layer is testable precisely because no model is involved, so it is the one
part of Bharosha that must be covered: the LLM's output cannot be asserted on,
but this can. Every case below is a message a user might plausibly type, in
Bangla, English, or romanised Bangla.

Run from bharosha_service/:  python -m pytest -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import referrals  # noqa: E402
import safety  # noqa: E402


# --- Emergencies: Bangla -------------------------------------------------

@pytest.mark.parametrize(
    "message, category",
    [
        ("আমাকে মারছে, বাঁচান", "immediate_danger"),
        ("আমার স্বামী আমাকে মারধর করছে", "active_violence"),
        ("সে আমাকে মেরে ফেলবে বলেছে", "threat_to_life"),
        ("ও আমাকে খুন করবে", "threat_to_life"),
        ("আমি আর বাঁচতে চাই না", "suicide_risk"),
        ("আত্মহত্যা করতে ইচ্ছে করছে", "suicide_risk"),
        ("আমি এখনই বিপদে আছি", "immediate_danger"),
        ("আমার মেয়েকে যৌন নির্যাতন করা হয়েছে", "child_disclosure"),
        ("আমার এলাকায় বাল্যবিবাহ হচ্ছে", "child_disclosure"),
        ("একটি শিশুকে ধর্ষণ করা হয়েছে", "child_disclosure"),
    ],
)
def test_bangla_emergencies(message: str, category: str) -> None:
    decision = safety.classify(message)
    assert decision.kind == "emergency"
    assert decision.category == category
    assert decision.language == "bn"
    assert decision.stops_turn


# --- Emergencies: English ------------------------------------------------

@pytest.mark.parametrize(
    "message, category",
    [
        ("He is beating me right now", "active_violence"),
        ("my husband just beat me", "active_violence"),
        ("I am not safe, please help me now", "immediate_danger"),
        ("He said he will kill me", "threat_to_life"),
        ("he threatened to kill me if I tell anyone", "threat_to_life"),
        ("I want to die", "suicide_risk"),
        ("I have been thinking about suicide", "suicide_risk"),
        ("I don't want to live anymore", "suicide_risk"),
        ("My daughter was touched by her teacher", "child_disclosure"),
        ("a child in our village is being abused", "child_disclosure"),
        ("she is only 14 and they want to marry her off", "child_disclosure"),
        # Regression: the pattern stem was "marri", which matches "marriage"
        # and "married" but not "marry" — the verb form people actually use.
        ("they want to marry off my daughter", "child_disclosure"),
        ("my daughter is being married off next month", "child_disclosure"),
        ("a child marriage is being arranged in our village", "child_disclosure"),
    ],
)
def test_english_emergencies(message: str, category: str) -> None:
    decision = safety.classify(message)
    assert decision.kind == "emergency"
    assert decision.category == category
    assert decision.language == "en"


# --- Emergencies: romanised Bangla --------------------------------------

@pytest.mark.parametrize(
    "message, category",
    [
        ("amake marche help", "active_violence"),
        ("se amake mere felbe", "threat_to_life"),
        ("ami morte chai", "suicide_risk"),
        ("ami bipode achi", "immediate_danger"),
    ],
)
def test_romanised_bangla_emergencies(message: str, category: str) -> None:
    decision = safety.classify(message)
    assert decision.kind == "emergency"
    assert decision.category == category
    # Latin script gets an English reply, which is what the user can read.
    assert decision.language == "en"


# --- The three forbidden subjects ---------------------------------------

@pytest.mark.parametrize(
    "message, category",
    [
        ("Should I leave my husband?", "leave_decision"),
        ("is it safe to leave now", "leave_decision"),
        ("আমি কি স্বামীকে ছেড়ে চলে যাব", "leave_decision"),
        ("আমি কি তালাক দেব", "leave_decision"),
        ("How do I collect evidence against him?", "confront_or_evidence"),
        ("should i record him", "confront_or_evidence"),
        ("আমি কি ভিডিও করে রাখব", "confront_or_evidence"),
        ("প্রমাণ জোগাড় করব কীভাবে", "confront_or_evidence"),
        ("Will I win the case?", "legal_advice"),
        ("what are my legal rights", "legal_advice"),
        ("মামলা করলে কি জিতব", "legal_advice"),
        ("কোন ধারায় মামলা হবে", "legal_advice"),
        # Regression: found by the near-topic retrieval controls, where both of
        # these reached the corpus instead of being refused. A leaving question
        # framed as a procedure is still a leaving question; an inheritance
        # question is a legal one, and sits so close to WaterAid's own text on
        # economic violence that no distance threshold could separate it.
        ("How do I get a divorce in Bangladesh?", "divorce_process"),
        ("বাংলাদেশে তালাক কীভাবে নেব?", "divorce_process"),
        ("what is the divorce process", "divorce_process"),
        ("What are a woman's inheritance rights in Bangladesh?", "economic_rights"),
        ("বাংলাদেশে নারীর উত্তরাধিকার অধিকার কী?", "economic_rights"),
        ("am I entitled to inherit my father's property?", "economic_rights"),
    ],
)
def test_refusals(message: str, category: str) -> None:
    decision = safety.classify(message)
    assert decision.kind == "refuse"
    assert decision.category == category
    assert decision.stops_turn


# --- Precedence ---------------------------------------------------------

@pytest.mark.parametrize(
    "forward, reversed_, category",
    [
        # Word order is the bug class this matcher exists to remove: each pair is
        # the same disclosure phrased with the two concepts swapped, and both must
        # land in the same category.
        ("my daughter was abused", "they abused my daughter", "child_disclosure"),
        ("a child was beaten", "someone beat a child", "child_disclosure"),
        ("আমার মেয়েকে নির্যাতন করা হয়েছে", "নির্যাতন করা হয়েছে আমার মেয়েকে",
         "child_disclosure"),
        ("inheritance rights for women", "entitled to inherit land", "economic_rights"),
        ("উত্তরাধিকারের অধিকার", "অধিকার আছে কি উত্তরাধিকারে", "economic_rights"),
        ("how do I collect evidence", "the evidence I need to collect",
         "confront_or_evidence"),
        # "complaint" left this rule deliberately — see reporting_request in
        # safety.py. "Where do I complain" is a question about where to go, and
        # the legal refusal answered it with "I cannot predict how a case would
        # turn out". Filing a CASE is still a legal question, and this is the
        # pair that checks it in both word orders.
        ("filing a case, should I", "should I file a case", "legal_advice"),
        # Found by auditing the remaining ordered patterns rather than by a
        # failing case: "right now I am scared" matched, "I am scared right now"
        # did not, and the second is how people actually write it.
        ("right now I am scared", "I am scared right now", "immediate_danger"),
        ("এখনই আমি ভয় পাচ্ছি", "আমি ভয় পাচ্ছি এখনই", "immediate_danger"),
    ],
)
def test_order_does_not_matter(forward: str, reversed_: str, category: str) -> None:
    """Both phrasings must classify identically — see safety.NearRule."""
    assert safety.classify(forward).category == category, f"forward: {forward}"
    assert safety.classify(reversed_).category == category, f"reversed: {reversed_}"


def test_near_rule_respects_its_window() -> None:
    """Co-occurrence is windowed, not document-wide, or every long message with
    the word 'child' anywhere in it would trip the child rule."""
    far_apart = (
        "my daughter asked about school and homework and dinner and bedtime "
        "and then we talked about the news where someone was abused"
    )
    assert safety.classify(far_apart).kind == "proceed"


def test_emergency_beats_refusal() -> None:
    """"He will kill me if I leave" is an emergency, not a leaving question."""
    decision = safety.classify("He will kill me if I leave him")
    assert decision.kind == "emergency"
    assert decision.category == "threat_to_life"
    assert "leave_decision" in decision.matched  # recorded, but did not win


def test_child_disclosure_beats_active_violence() -> None:
    decision = safety.classify("my daughter is being beaten by her father")
    assert decision.category == "child_disclosure"


def test_suicide_risk_wins_when_combined() -> None:
    decision = safety.classify("he beats me and I want to die")
    assert decision.category == "suicide_risk"


# --- Ordinary questions must pass through -------------------------------

@pytest.mark.parametrize(
    "message",
    [
        "What is safeguarding?",
        "What is gender-based violence?",
        "Who is responsible for safeguarding?",
        "সেফগার্ডিং মানে কী",
        "জেন্ডারভিত্তিক সহিংসতা কী",
        "What are the myths about GBV?",
        "How can violence be prevented in a community?",
        "Tell me about WaterAid's safeguarding principles",
        # Short but real. There is deliberately no "too short to answer" rule —
        # these are the queries it would have swallowed.
        "sexual harassment",
        "economic violence",
    ],
)
def test_ordinary_questions_proceed(message: str) -> None:
    decision = safety.classify(message)
    assert decision.kind == "proceed"
    assert decision.category is None
    assert not decision.stops_turn


@pytest.mark.parametrize(
    "message",
    ["hi", "hello", "Hello!", "assalamu alaikum", "good morning",
     "নমস্কার", "হ্যালো", "আসসালামু আলাইকুম",
     # "How are you" opens a conversation in Bangla; it is not a question about
     # the software. This is the message that exposed the whole gap: it used to
     # return the no-context reply, topic list and helplines included.
     "how are you?", "kemon acho?", "kemon achen", "ki khobor",
     "কেমন আছো?", "আপনি কেমন আছেন", "কী খবর"],
)
def test_greetings_are_recognised(message: str) -> None:
    """Recognised, but NOT answered on the device any more.

    A greeting goes to the model like everything else outside
    safety.DEVICE_CATEGORIES — a saved "Hello. Ask me anything about
    safeguarding…" every single time is what made the app read as canned. The
    category still exists because it is the offline fallback: when the model
    cannot be reached, this is the text she gets.
    """
    decision = safety.classify(message)
    assert decision.kind == "social"
    assert decision.category == "greeting"
    assert not decision.stops_turn, "a greeting no longer bypasses the model"
    assert referrals.response_for("greeting", decision.language)


@pytest.mark.parametrize(
    "message, category",
    [
        ("hi, he is beating me", "active_violence"),
        ("hello, should I leave my husband?", "leave_decision"),
        ("নমস্কার, আমাকে মারছে", "active_violence"),
    ],
)
def test_a_greeting_that_carries_a_disclosure_is_not_a_greeting(
    message: str, category: str
) -> None:
    """Greeting sits last in the priority order for exactly this reason."""
    assert safety.classify(message).category == category


def test_language_detection() -> None:
    assert safety.detect_language("What is safeguarding?") == "en"
    assert safety.detect_language("সেফগার্ডিং কী") == "bn"
    # One Bangla clause in a mixed sentence is still answered in Bangla.
    assert safety.detect_language("safeguarding মানে কী") == "bn"


def test_normalise_strips_invisible_characters() -> None:
    """Zero-width joiners must not let a message slip past the patterns."""
    assert safety.classify("আমাকে মার​ছে").kind == "emergency"
    assert safety.classify("I want‌ to die").kind == "emergency"


# --- Every category has usable hardcoded text --------------------------

@pytest.mark.parametrize("category", safety.EMERGENCY_CATEGORIES + safety.REFUSAL_CATEGORIES)
@pytest.mark.parametrize("language", ["en", "bn"])
def test_every_category_has_a_response(category: str, language: str) -> None:
    text = referrals.response_for(category, language)
    assert text.strip(), f"{category}/{language} is empty"
    # Every stop-the-turn reply must carry at least one real number.
    assert any(line.number in text for line in referrals.NATIONAL_HELPLINES)


@pytest.mark.parametrize("language", ["en", "bn"])
def test_emergency_replies_carry_999_and_109(language: str) -> None:
    for category in ("immediate_danger", "active_violence", "threat_to_life"):
        text = referrals.response_for(category, language)
        assert "999" in text
        assert "109" in text


@pytest.mark.parametrize("language", ["en", "bn"])
def test_child_disclosure_routes_to_child_helpline(language: str) -> None:
    text = referrals.response_for("child_disclosure", language)
    assert "1098" in text
    assert referrals.SAFEGUARDING_EMAIL in text


@pytest.mark.parametrize("language", ["en", "bn"])
def test_no_script_sends_anyone_to_16263(language: str) -> None:
    """16263 is labelled a GBV hotline in the app but appears to be the
    national health line. Until WaterAid confirms, it stays out of every
    hardcoded referral."""
    for category in safety.EMERGENCY_CATEGORIES + safety.REFUSAL_CATEGORIES + ("no_context",):
        assert "16263" not in referrals.response_for(category, language)


def test_16263_is_still_in_the_contacts_list() -> None:
    """Flagged, not deleted: removing a number is also a change WaterAid owns."""
    numbers = [line.number for line in referrals.NATIONAL_HELPLINES]
    assert numbers == ["999", "109", "16263", "1098", "333"]
    assert referrals.helpline("16263").in_emergency_script is False


def test_referral_list_matches_the_app() -> None:
    assert len(referrals.SAFEGUARDING_FOCAL_POINTS) == 9
    assert referrals.helpline("109").number == "109"
    with pytest.raises(KeyError):
        referrals.helpline("16430")  # not in the app's list; not invented here
