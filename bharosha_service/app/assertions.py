"""Scans a below-floor reply for the thing it was told not to do.

THE SAME PRINCIPLE AS safety.py, APPLIED TO THE OTHER END. Do not trust the
model — check. There, the rule is that emergency detection never depends on a
model; here, the rule is that a model's compliance with a prohibition is never
taken on faith.

WHY THIS EXISTS. Below the relevance floor the prompt tells the model it may
converse and ask one question but may NOT state any safeguarding, health, legal
or procedural fact. Measured, it obeys that most of the time and not all of the
time: "ki korbo?" came back once as a clarifying question and once as a numbered
list of steps for helping an abused person. Temperature 0 made it repeatable
rather than compliant, and more prompt text moved the failure around rather than
removing it. A 20B model will not hold a prohibition perfectly, so the
prohibition is enforced after the fact.

WHAT HAPPENS ON A MATCH. The generated text is DISCARDED — not edited, not
truncated, not re-asked. The caller returns the hardcoded referral, which is the
same thing that happens when the model is unreachable. A reply that broke the
rule is not evidence about what the right reply was.

This runs ONLY below the floor. Above it the model is licensed to answer from
WaterAid's material, and that material is full of legitimate numbered steps.
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
    r"\b(first|firstly|secondly|next|then|finally)\s*,",
    r"\bthe\s+(first|next|safest|best)\s+step\b",
    r"\bhere'?s\s+what\s+you\s+can\s+do\b",
    r"\bi\s+(would\s+)?(recommend|suggest|advise)\b",
    r"\bit\s+is\s+important\s+to\b",
    r"\btry\s+to\s+(tell|talk|speak|contact|reach|keep|record)\b",
    r"\byou\s+can\s+(report|file|apply|claim|demand|collect)\b",
    r"\bencourage\s+(her|him|them)\s+to\b",
    # Bangla. No \b — see the guard in safety.py for why it never matches here.
    r"আপনার\s*উচিত",
    r"আপনি\s*(করতে|করা)\s*পারেন",
    r"প্রথমে\s*,?\s*(আপনি|তাকে)",
    r"(প্রথম|পরবর্তী|সবচেয়ে\s*নিরাপদ)\s*(ধাপ|পদক্ষেপ)",
    r"আমি\s*(পরামর্শ|সুপারিশ)\s*দিচ্ছি",
    r"নিশ্চিত\s*করুন",
    r"(করা|জানানো|যোগাযোগ\s*করা)\s*(খুব\s*)?(জরুরি|গুরুত্বপূর্ণ)",
)

_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in _LIST_MARKERS + _ADVISORY)


class _Counter:
    """How often the check has fired since the process started.

    A COUNT, and nothing else. No text, no session id, no category, nothing
    timestamped — the same rule that governs every other number this service
    keeps. It exists because "the model breaks the rule sometimes" is not a
    finding until it has a number attached to it.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.checked = 0
        self.discarded = 0

    def record(self, discarded: bool) -> None:
        with self._lock:
            self.checked += 1
            self.discarded += discarded

    def snapshot(self) -> dict[str, int | float]:
        with self._lock:
            rate = self.discarded / self.checked if self.checked else 0.0
            return {
                "ungrounded_replies_checked": self.checked,
                "ungrounded_replies_discarded": self.discarded,
                "discard_rate": round(rate, 3),
            }


counter = _Counter()


def asserts_anyway(text: str) -> str | None:
    """The first marker found in a below-floor reply, or None if it is clean."""
    for pattern in _PATTERNS:
        match = pattern.search(text or "")
        if match:
            return match.group(0).strip()[:40]
    return None
