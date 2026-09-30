"""Checks a model-written reply for the things it was told not to do.

THE SAME PRINCIPLE AS safety.py, APPLIED TO THE OTHER END. Do not trust the
model — check. There, the rule is that emergency detection never depends on a
model; here, the rule is that a model's compliance with a prohibition is never
taken on faith.

TWO CHECKS.

  contains_contact  — any run of three or more digits, or any "@". Runs on
                      EVERY model-written reply, grounded or not, because the
                      model must never write a phone number or an email: the
                      numbers arrive from referrals.py, appended by code, so
                      that a wrong digit in a helpline is structurally
                      impossible. This one has no exceptions.

  gives_advice      — numbered or bulleted step lists, and the clearly
                      advisory shapes ("you should", "make sure to", "here's
                      what you can do", and their Bangla). Runs when a safety
                      category matched, and on any reply below the relevance
                      floor. NOT on an ordinary grounded answer with no
                      category: WaterAid's material is full of legitimate
                      numbered steps, and the model is licensed to relay them.

WHAT WAS REMOVED, AND WHY. The first version of this check also fired on
"first,", "next,", "it is important to", "আপনি করতে পারেন" and "জানানো
জরুরি". Measured, those caught gentle sentences that were not advice — "it is
important to me that you know this isn't your fault" — and swapped in fixed
text for about one reply in ten. A check that punishes kindness is the old
problem wearing a new badge. The patterns that remain fire on the shape of
instruction, not on warmth.

WHAT HAPPENS ON A MATCH. The caller retries ONCE, with a line added above the
user's message saying what went wrong (chain.RETRY_NOTE). If the retry also
fails, the fixed fallback text is sent. Retries and fallbacks are counted
separately at /health, because they are different findings: a retry means the
prompt is slightly loose, a fallback means the model could not be steered.
"""

from __future__ import annotations

import re
import threading

# Ordered lists and numbered steps. The clearest signal there is: a
# conversational reply to "ki korbo?" does not have a step 2.
_LIST_MARKERS = (
    r"(?m)^\s*\d+[.)]\s+\S",
    r"(?m)^\s*[-*•]\s+\S",
    r"(?m)^\s*\*\*\d+[.)]",
)

# Advice and instruction, in English and in Bangla. Deliberately blunt: this
# fires on the shape of advice, not on its content, because the content is
# exactly what cannot be judged mechanically.
_ADVISORY = (
    r"\byou\s+should\b",
    r"\byou\s+(must|need\s+to|ought\s+to|have\s+to)\b",
    r"\bmake\s+sure\s+(to|that|you)\b",
    r"\bthe\s+(first|next|safest|best)\s+step\b",
    r"\bhere'?s\s+what\s+you\s+can\s+do\b",
    r"\bi\s+(would\s+)?(recommend|suggest|advise)\b",
    r"\btry\s+to\s+(tell|talk|speak|contact|reach|keep|record)\b",
    r"\byou\s+can\s+(report|file|apply|claim|demand|collect)\b",
    r"\bencourage\s+(her|him|them)\s+to\b",
    # Bangla. No \b — see the guard in safety.py for why it never matches here.
    r"আপনার\s*উচিত",
    r"প্রথমে\s*,?\s*(আপনি|তাকে)",
    r"(প্রথম|পরবর্তী|সবচেয়ে\s*নিরাপদ)\s*(ধাপ|পদক্ষেপ)",
    r"আমি\s*(পরামর্শ|সুপারিশ)\s*দিচ্ছি",
    r"নিশ্চিত\s*করুন",
    # Bangla imperatives that are instructions to act: "talk to…", "contact…",
    # "go to…". "কল করুন" is deliberately absent — the vague note asks the
    # model to say the call buttons are there, and that is the verb it uses.
    r"(কথা\s*বলুন|যোগাযোগ\s*করুন|চলে\s*যান|জমা\s*দিন|সংগ্রহ\s*করুন)",
)

_ADVICE_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in _LIST_MARKERS + _ADVISORY)

# A phone number, short code, email or web address the model wrote itself.
# Three digits is the shortest helpline (109), so three is the threshold.
# Bangla digits count too — ৯৯৯ is 999. URLs were added after a live run: a
# reporting question in Bangla came back grounded on staff-facing material,
# naming a UK "Safecall" website and how to file — no digits, no "@", and it
# would have passed. A web address is a contact.
_CONTACT = re.compile(
    r"[0-9০-৯]{3,}"
    r"|@"
    r"|https?://|www\."
    r"|\b[a-z0-9-]+\.(?:com|org|net|gov|edu|bd|uk|co\.uk|info|io)\b",
    re.IGNORECASE,
)


def contains_contact(text: str) -> str | None:
    """The first number or email in a reply, or None. No exceptions."""
    match = _CONTACT.search(text or "")
    return match.group(0) if match else None


def gives_advice(text: str) -> str | None:
    """The first advisory or list marker in a reply, or None."""
    for pattern in _ADVICE_PATTERNS:
        match = pattern.search(text or "")
        if match:
            return match.group(0).strip()[:40]
    return None


def check(text: str, advisory: bool) -> str | None:
    """Everything wrong with a reply, or None if it may be shown.

    `advisory` says whether the advice check applies — True when a safety
    category matched or the reply is below the floor. The contact check always
    applies.
    """
    contact = contains_contact(text)
    if contact:
        return f"contact {contact!r}"
    if advisory:
        marker = gives_advice(text)
        if marker:
            return f"advice {marker!r}"
    return None


# The legacy name, kept for the tests and tools that call it.
asserts_anyway = gives_advice


class _Counter:
    """How often the check has fired since the process started.

    COUNTS, and nothing else. No text, no session id, no category, nothing
    timestamped — the same rule that governs every other number this service
    keeps. Retries and fallbacks are separate because they are different
    findings: a retry means the prompt is slightly loose, a fallback means the
    model could not be steered.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.checked = 0
        self.retried = 0
        self.fell_back = 0

    def record(self, retried: bool = False, fell_back: bool = False) -> None:
        with self._lock:
            self.checked += 1
            self.retried += retried
            self.fell_back += fell_back

    def snapshot(self) -> dict[str, int | float]:
        with self._lock:
            n = self.checked or 1
            return {
                "output_checks": self.checked,
                "output_retries": self.retried,
                "output_fallbacks": self.fell_back,
                "retry_rate": round(self.retried / n, 3),
                "fallback_rate": round(self.fell_back / n, 3),
            }


counter = _Counter()
