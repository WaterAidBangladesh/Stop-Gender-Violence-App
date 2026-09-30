"""The prompt and its slots. Pure, offline, no model.

What the model is told is the one part of this service that cannot be unit
tested for behaviour, so these pin the things that can be checked: that every
prohibition is still in the text, that every category has its note, that the
slots resolve, and that nothing from the old prompt leaks through.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import chain  # noqa: E402
import referrals  # noqa: E402
import safety  # noqa: E402


def test_the_prompt_ends_with_no_preamble() -> None:
    assert chain.PROMPT.rstrip().endswith("(NO PREAMBLE)")


def test_the_seven_limits_are_all_present() -> None:
    """Numbered so they can be audited against the brief."""
    for n, fragment in [
        (1, "Never advise whether or when to leave"),
        (2, "Never give legal advice or predict how a case would turn out"),
        (3, "Never suggest confronting, reasoning with, recording or gathering evidence"),
        (4, "Never write a phone number, short code, hotline number or email address"),
        (5, "Never say or imply that this app can take, record or pass on a report"),
        (6, "Never ask for names, places, dates or anything that could identify anyone"),
        (7, "Never give step-by-step instructions or numbered lists"),
    ]:
        assert f"{n}. {fragment}" in chain.PROMPT, f"limit {n} is missing or reworded"


def test_the_escape_hatch_is_not_in_the_prompt() -> None:
    """The one line deliberately not copied from the reference project."""
    assert "Flow of Chat" not in chain.PROMPT
    assert "create an informed and relevant response" not in chain.PROMPT
    assert "say so plainly and kindly" in chain.PROMPT


def test_the_old_reminder_slot_is_gone() -> None:
    """Part B's grounding line replaces the reminder that used to be repeated
    above the user message."""
    assert "{reminder}" not in chain.PROMPT
    assert "{grounding_line}" in chain.PROMPT
    assert "{app_note}" in chain.PROMPT
    assert "{examples}" in chain.PROMPT
    assert "{retry_note}" in chain.PROMPT


def test_every_slot_resolves() -> None:
    """A template variable with nothing to fill it raises at invoke time — in
    front of a user. Render the template here with every value present."""
    from langchain_core.prompts import PromptTemplate

    template = PromptTemplate.from_template(chain.PROMPT)
    expected = {
        "grounding_line", "app_note", "examples", "retry_note",
        "context", "history", "question", "language", "language_caps",
    }
    assert set(template.input_variables) == expected
    rendered = template.format(
        grounding_line=chain.GROUNDED_LINE,
        app_note=chain.app_note("leave_decision", "full"),
        examples=chain.EXAMPLES,
        retry_note="",
        context="none",
        history="none",
        question="hi",
        language="English",
        language_caps="ENGLISH",
    )
    assert "{" not in rendered.replace("{block}", ""), "an unresolved slot survived"


def test_every_model_answered_category_has_an_app_note() -> None:
    for category in safety._PRIORITY:
        if category in safety.DEVICE_CATEGORIES:
            continue
        assert category in chain.APP_NOTES, f"no app note for {category}"


def test_app_notes_and_blocks_agree_about_what_is_shown() -> None:
    """A note that promises a block must belong to a category that has one,
    and a note that says nothing is shown must belong to one that does not."""
    for category, note in chain.APP_NOTES.items():
        promises_block = "{block}" in note
        assert promises_block == referrals.has_block(category), category


def test_the_block_phrase_is_substituted() -> None:
    full = chain.app_note("personal_disclosure", "full")
    compact = chain.app_note("personal_disclosure", "compact")
    assert "{block}" not in full and "{block}" not in compact
    assert "the full contacts block" in full
    assert "a one-line reminder of the helpline" in compact
    assert chain.app_note(None, None) == chain.NO_CATEGORY_NOTE
    assert "{block}" not in chain.app_note("greeting", None)


def test_a_block_category_without_a_mode_is_refused() -> None:
    with pytest.raises(ValueError):
        chain.app_note("leave_decision", None)


def test_examples_carry_no_phone_numbers() -> None:
    """They teach tone; a number in them would teach the model to write one."""
    import re

    assert not re.search(r"\d{3,}", chain.EXAMPLES)
    assert "@" not in chain.EXAMPLES


def test_the_automatic_footer_is_gone() -> None:
    """Numbers now arrive only as a referral block, only when a category
    matched. There is no footer constant left to append by accident."""
    assert not hasattr(referrals, "answer_footer")
    assert not hasattr(referrals, "ANSWER_FOOTER_EN")
