"""Deterministic safety layer. Runs before the model, and can stop the turn.

The rule this module exists to enforce: **the model is never the safety layer.**
Emergency detection is plain pattern matching in Python, so its behaviour is
fixed, inspectable and testable. An LLM asked to spot an emergency will
sometimes miss one, and a miss here means a person in danger gets a paragraph
about safeguarding principles instead of a phone number.

Three outcomes:

* ``emergency`` — return the hardcoded referral. Do not call the model, do not
  retrieve. Matching is deliberately broad: a false positive shows someone a
  helpline number they did not need, which is survivable. A false negative is
  not.
* ``refuse``  — one of the three forbidden subjects. Refuse warmly with a
  referral, again without retrieving, so no retrieved passage can be shaped
  into a partial answer.
* ``proceed`` — safe to retrieve and answer from the corpus.

Patterns cover Bangla script, English, and romanised Bangla ("amake marche"),
because users mix all three in one sentence. Bangla has no case, so
normalisation is about Unicode form and stray joiners, not casefolding.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Categories that stop the turn and return a referral.
EMERGENCY_CATEGORIES = (
    "suicide_risk",
    "immediate_danger",
    "threat_to_life",
    "child_disclosure",
    "active_violence",
)

# Categories that stop the turn and return a refusal plus a referral.
REFUSAL_CATEGORIES = (
    "leave_decision",
    "divorce_process",
    "confront_or_evidence",
    "economic_rights",
    "legal_advice",
)

# Evaluation order, not a ranking of severity. The first match wins so the
# outcome for a given message never depends on dict ordering or regex speed.
# Emergencies are checked before refusals: "he will kill me if I leave" is an
# emergency, not a question about leaving.
_PRIORITY = EMERGENCY_CATEGORIES + REFUSAL_CATEGORIES

# Zero-width joiners and marks that break naive matching on Bangla text.
_INVISIBLE = re.compile(r"[​‌‍﻿]")
_WHITESPACE = re.compile(r"\s+")

# Any character in the Bengali block.
_BENGALI = re.compile(r"[ঀ-৿]")


def normalise(text: str) -> str:
    """Fold a message to the form the patterns are written against."""
    text = unicodedata.normalize("NFC", text)
    text = _INVISIBLE.sub("", text)
    text = text.lower()  # affects Latin only; Bangla has no case
    return _WHITESPACE.sub(" ", text).strip()


def detect_language(text: str) -> str:
    """'bn' if the message contains Bangla script, else 'en'.

    Script presence, not proportion: a sentence with one Bangla clause in it is
    answered in Bangla. Romanised Bangla is answered in English, which is what
    someone typing Latin characters can read.
    """
    return "bn" if _BENGALI.search(text) else "en"


# --- Patterns ------------------------------------------------------------
#
# Grouped by category and kept flat and readable on purpose: this table is the
# safety behaviour, and a reviewer with no Python should be able to audit it.
# Bangla entries come first in each list, then English, then romanised.

_PATTERNS: dict[str, tuple[str, ...]] = {
    "suicide_risk": (
        r"আত্মহত্যা",
        r"আত্মহনন",
        r"মরে\s*যেতে\s*চাই",
        r"মরতে\s*চাই",
        r"বাঁচতে\s*চাই\s*না",
        r"বেঁচে\s*থাকতে\s*চাই\s*না",
        r"নিজেকে\s*শেষ\s*করে",
        r"জীবন\s*শেষ\s*করে\s*দি",
        r"\bsuicid(e|al)\b",
        r"\bkill\s+myself\b",
        r"\bend\s+my\s+life\b",
        r"\bwant\s+to\s+die\b",
        r"\bdon'?t\s+want\s+to\s+live\b",
        r"\bharm\s+myself\b",
        r"\bhurt\s+myself\b",
        r"\battohotta\b",
        r"\bmorte\s*chai\b",
        r"\bbachte\s*chai\s*na\b",
    ),
    "immediate_danger": (
        r"এখনই\s*বিপদে",
        r"এখন\s*বিপদে",
        r"বিপদে\s*আছি",
        r"ভয়\s*পাচ্ছি",
        r"লুকিয়ে\s*আছি",
        r"দরজা\s*ভাঙ",
        r"বাঁচাও",
        r"বাঁচান",
        r"সাহায্য\s*দরকার\s*এখনই",
        # "right now" before the fear word only — see the immediate_danger
        # NearRule, which covers "I am scared right now" too. Kept because it
        # also matches phrasings the window rule would not, e.g. punctuation-run
        # sentences with no space-separated tokens between them.
        r"\bright\s+now\b.{0,30}\b(danger|unsafe|afraid|scared)\b",
        r"\b(in|im|i'?m)\s+(immediate\s+)?danger\b",
        r"\bnot\s+safe\b",
        r"\bunsafe\s+(right\s+)?now\b",
        r"\bhiding\s+from\b",
        r"\bhelp\s+me\s+now\b",
        r"\bbreaking\s+(down\s+)?the\s+door\b",
        r"\bbipode\b",
        r"\bbachao\b",
    ),
    "threat_to_life": (
        r"মেরে\s*ফেলবে",
        r"খুন\s*করবে",
        r"হত্যা\s*করবে",
        r"মেরে\s*ফেলার\s*ভয়",
        r"জানে\s*মেরে",
        r"অ্যাসিড",
        r"এসিড\s*মার",
        r"গলা\s*টিপে",
        r"\b(will|going\s+to|gonna)\s+kill\s+me\b",
        r"\bthreaten(ed|ing)?\s+to\s+kill\b",
        r"\bdeath\s+threat",
        r"\bacid\s+attack\b",
        r"\bstrangl(e|ed|ing)\b",
        r"\bmere\s*felbe\b",
        r"\bkhun\s*korbe\b",
    ),
    "child_disclosure": (
        r"আমার\s*(মেয়ে|ছেলে|সন্তান|বাচ্চা)(কে|র)?\s*(সাথে|সঙ্গে)?\s*.{0,20}(নির্যাতন|মার|ধর্ষণ|স্পর্শ|হয়রানি|যৌন)",
        r"(শিশু|বাচ্চা|নাবালিকা|নাবালক|অপ্রাপ্তবয়স্ক)\s*.{0,25}(নির্যাতন|ধর্ষণ|যৌন|মারধর|হয়রানি|বিয়ে)",
        r"বাল্যবিবাহ",
        r"বাল্য\s*বিয়ে",
        r"স্কুলে\s*.{0,25}(শিক্ষক|স্যার).{0,25}(স্পর্শ|যৌন|হয়রানি)",
        # "marr" on purpose, not "marri": people say "marry her off" and
        # "married off" as often as "marriage", and a stem that misses the verb
        # form misses most real child-marriage disclosures.
        r"\b(my\s+)?(daughter|son|child|kid)\b.{0,40}\b(abus|beat|rape|touch|harass|molest|hit|marr)",
        r"\b(child|minor|underage|under\s*18|teenage)\b.{0,40}\b(abus|rape|sexual|harass|molest|marr)",
        # The harm can also come first: "marry off my daughter", "beating a
        # child". This direction accepts some false positives — a definitional
        # question like "what is child abuse?" gets the referral instead of a
        # corpus answer. That trade is deliberate: the cost is one unhelpful
        # reply, and the cost of the reverse is a missed disclosure.
        r"\b(marr|abus|rape|molest|harass|beat|traffick)\w*\b.{0,40}\b(my\s+)?(daughter|son|child|kid)\b",
        r"\bchild\s+(marriage|abuse|sexual\s+abuse)\b",
        r"\b(a\s+)?(student|pupil)\b.{0,30}\b(teacher|sir)\b.{0,30}\b(touch|sexual|harass)",
        r"\b(she|he)\s+is\s+(only\s+)?(\d|1[0-7])\s*(years?\s*old)?\b.{0,40}\b(abus|rape|beat|marr|touch)",
    ),
    "active_violence": (
        r"মারছে",
        r"মারধর\s*করছে",
        r"মারতে\s*আসছে",
        r"পিটিয়েছে",
        r"ধর্ষণ\s*করছে",
        r"ধর্ষণ\s*করেছে",
        r"জোর\s*করে\s*.{0,15}(সহবাস|শারীরিক)",
        r"রক্ত\s*(পড়ছে|ঝরছে)",
        r"\b(he|she|they)\s+is\s+(beating|hitting|attacking|choking)\b",
        r"\b(beating|attacking|hitting)\s+me\s+(right\s+)?now\b",
        r"\bjust\s+(beat|hit|attacked|raped)\s+me\b",
        r"\bbeing\s+(raped|attacked|assaulted)\b",
        r"\bi\s+am\s+bleeding\b",
        r"\bamake\s+marche\b",
        r"\bmar\s*dhor\s*korche\b",
    ),
    "leave_decision": (
        r"(ছেড়ে|ছাড়ে)\s*(চলে\s*)?(যাব|যাওয়া|দেব)",
        r"বাড়ি\s*ছেড়ে",
        r"স্বামীকে\s*ছেড়ে",
        r"চলে\s*যাওয়া\s*উচিত",
        r"পালিয়ে\s*যাব",
        r"তালাক\s*(দেব|নেব|দেওয়া\s*উচিত)",
        r"ডিভোর্স\s*(দেব|নেব|দেওয়া\s*উচিত)",
        r"\bshould\s+i\s+(leave|divorce|separate|move\s+out|run\s+away)\b",
        r"\b(leave|divorce)\s+(my\s+)?(husband|wife|partner|him|her)\b",
        r"\b(is\s+it|when\s+is)\s+.{0,20}\b(safe|right)\s+(time\s+)?to\s+leave\b",
        r"\bshould\s+i\s+stay\s+or\s+(go|leave)\b",
        r"\bmove\s+out\s+of\s+(the\s+)?(house|home)\b",
    ),
    # Separate from leave_decision for TONE, not mechanism — both are refusals
    # with per-category text. Someone asking HOW to get a divorce has already
    # decided; answering her with "I can't advise you on whether to leave" reads
    # as being shut down. See referrals.REFUSE_DIVORCE_EN.
    #
    # Found by the near-topic controls: every leaving pattern assumed a decision
    # framing ("should I…"), so a procedural framing ("how do I…") walked past all
    # of them and reached the corpus.
    "divorce_process": (
        r"\bhow\s+(do|can|would)\s+i\s+(get|file\s+for|apply\s+for|start)\s+a?\s*(divorce|separation|khula)\b",
        r"\b(divorce|separation|khula)\s+(process|procedure|rules?|law|papers)\b",
        r"\bwhat\s+(is|are)\s+the\s+(divorce|separation)\s+(process|procedure|rules?)\b",
        r"(তালাক|ডিভোর্স|খুলা)\s*.{0,15}(কীভাবে|কিভাবে|নিয়ম|প্রক্রিয়া|পদ্ধতি|কাগজ)",
        r"(কীভাবে|কিভাবে)\s*.{0,15}(তালাক|ডিভোর্স|খুলা)",
    ),
    "confront_or_evidence": (
        r"প্রমাণ\s*(জোগাড়|সংগ্রহ|যোগাড়)",
        r"রেকর্ড\s*কর",
        r"ভিডিও\s*কর",
        r"মুখোমুখি\s*হব",
        r"তাকে\s*বোঝাব",
        r"তার\s*সাথে\s*কথা\s*বলে\s*ঠিক",
        r"স্ক্রিনশট\s*(নেব|রাখব)",
        r"\b(collect|gather|get)\s+(evidence|proof)\b",
        r"\b(record|film|video)\s+(him|her|them|the\s+abuse)\b",
        r"\bconfront\b",
        r"\bshould\s+i\s+(talk|reason)\s+with\s+(him|her|them)\b",
        r"\bprove\s+(that\s+)?(he|she|they)\b",
        r"\btake\s+(a\s+)?screenshot",
        r"\bcatch\s+him\b",
    ),
    "legal_advice": (
        r"মামলা\s*(করব|করলে|দিলে|জিত)",
        r"মামলার\s*ফল",
        r"আইনত\s*কি",
        r"কোন\s*ধারায়",
        r"শাস্তি\s*(কি|কী|হবে|পাবে)",
        r"জিডি\s*(করব|করলে)",
        r"\blegal(ly)?\s+(advice|position|right)\b",
        r"\b(file|filing)\s+a\s+(case|complaint|fir|gd)\b.{0,30}\b(should|how|will|win|chance)\b",
        r"\bwill\s+i\s+win\b",
        r"\bwhat\s+(are\s+)?my\s+(legal\s+)?rights\b",
        # Inheritance and property questions are NOT here: they moved to the
        # economic_rights co-occurrence rule, which recognises the harm before
        # referring, because WaterAid's own text lists "denying property or
        # inheritance rights" as economic violence.
        r"\bwhich\s+(section|law)\b",
        r"\bhow\s+much\s+(punishment|sentence)\b",
        r"\bcourt\s+(case|outcome|decide)\b",
    ),
}

_COMPILED: dict[str, tuple[re.Pattern[str], ...]] = {
    category: tuple(re.compile(p) for p in patterns)
    for category, patterns in _PATTERNS.items()
}


# --- Unordered co-occurrence rules -----------------------------------------
#
# WHY THIS EXISTS. Two separate misses came from the same mistake: an ordered
# pattern for a concept that has no fixed order.
#
#   "my daughter was abused"        matched      "they abused my daughter"  missed
#   "inheritance … entitled"        matched      "entitled to inherit"      missed
#
# Both were fixed by writing a second pattern for the other direction, which is
# fixing instances of a bug class rather than the class. A rule here matches two
# groups of terms co-occurring within a window of words, IN EITHER ORDER, so the
# order simply stops being expressible — and therefore stops being wrong.
#
# Ordered regexes remain above for concepts where order IS the meaning: "he will
# kill me" and "I will kill him" are not the same disclosure, and a window rule
# could not tell them apart.


@dataclass(frozen=True)
class NearRule:
    """Two term groups occurring within `window` words of each other, any order."""

    category: str
    first: tuple[str, ...]
    second: tuple[str, ...]
    window: int = 8
    note: str = ""


_CHILD_WORDS = (
    "daughter", "son", "child", "children", "kid", "minor", "underage", "teenage",
    "pupil", "student",
    "মেয়ে", "ছেলে", "সন্তান", "বাচ্চা", "শিশু", "নাবালিক", "নাবালক",
    "অপ্রাপ্তবয়স্ক", "কিশোরী", "কিশোর",
)

_HARM_WORDS = (
    "abus", "beat", "rape", "molest", "harass", "assault", "hit", "touch",
    "traffick", "marr",
    "নির্যাতন", "ধর্ষণ", "যৌন", "মারধর", "হয়রানি", "বিয়ে", "স্পর্শ", "পাচার",
)

_NEAR_RULES: tuple[NearRule, ...] = (
    NearRule(
        category="immediate_danger",
        first=("now", "currently", "এখন", "এখনই"),
        second=("danger", "unsafe", "afraid", "scared", "terrified", "hiding",
                "বিপদ", "ভয়", "লুকিয়ে", "নিরাপদ"),
        window=6,
        note=(
            "found by the pattern audit: the ordered version matched 'right now "
            "I am scared' but missed 'I am scared right now', which is the more "
            "natural phrasing"
        ),
    ),
    NearRule(
        category="child_disclosure",
        first=_CHILD_WORDS,
        second=_HARM_WORDS,
        note="a child and a harm in the same breath, whichever comes first",
    ),
    NearRule(
        category="economic_rights",
        first=("inherit", "inheritance", "property", "land", "dowry",
               "উত্তরাধিকার", "সম্পত্তি", "জমি", "যৌতুক"),
        second=("right", "entitled", "entitlement", "share", "claim", "deny",
                "denied", "law", "legal",
                "অধিকার", "ভাগ", "দাবি", "আইন", "বঞ্চিত"),
        note="inheritance/property entitlement, either order",
    ),
    NearRule(
        category="confront_or_evidence",
        first=("evidence", "proof", "screenshot", "recording",
               "প্রমাণ", "রেকর্ড", "স্ক্রিনশট"),
        second=("collect", "gather", "get", "keep", "take", "save", "need",
                "সংগ্রহ", "জোগাড়", "যোগাড়", "রাখব", "নেব"),
        note="evidence-gathering, either order",
    ),
    NearRule(
        category="legal_advice",
        first=("case", "complaint", "fir", "lawsuit", "court",
               "মামলা", "অভিযোগ", "আদালত", "কেস"),
        second=("file", "filing", "win", "chance", "outcome", "should", "punish",
                "করব", "করলে", "জিতব", "ফল", "শাস্তি"),
        note="filing or predicting a case, either order",
    ),
)


def _matches_term(token: str, term: str) -> bool:
    """Prefix match for Latin terms, substring for Bangla.

    "hit" as a prefix matches "hitting" but not "white"; Bangla inflects by
    suffixing, so "মার" must match inside "মারছে" and "মেয়ে" inside "মেয়েকে".
    """
    if term.isascii():
        return token.startswith(term)
    return term in token


def _near_match(tokens: list[str], rule: NearRule) -> bool:
    firsts = [
        i for i, token in enumerate(tokens)
        if any(_matches_term(token, term) for term in rule.first)
    ]
    if not firsts:
        return False
    seconds = [
        i for i, token in enumerate(tokens)
        if any(_matches_term(token, term) for term in rule.second)
    ]
    return any(
        i != j and abs(i - j) <= rule.window for i in firsts for j in seconds
    )


@dataclass(frozen=True)
class Decision:
    """What the safety layer decided about one message.

    ``matched`` lists every category that fired, for counter-only analytics.
    It is never stored next to message text, a session id, or anything about
    the user — see the logging rules in api.py.
    """

    kind: str  # "emergency" | "refuse" | "proceed"
    category: str | None
    language: str
    matched: tuple[str, ...]

    @property
    def stops_turn(self) -> bool:
        """True when the model must not be called at all."""
        return self.kind in ("emergency", "refuse")


def classify(message: str) -> Decision:
    """Classify one user message. Pure, deterministic, no I/O, no model."""
    language = detect_language(message)
    text = normalise(message)
    tokens = text.split()

    def fires(category: str) -> bool:
        if any(pattern.search(text) for pattern in _COMPILED.get(category, ())):
            return True
        return any(
            _near_match(tokens, rule)
            for rule in _NEAR_RULES
            if rule.category == category
        )

    matched = tuple(category for category in _PRIORITY if fires(category))

    for category in _PRIORITY:
        if category in matched:
            kind = "emergency" if category in EMERGENCY_CATEGORIES else "refuse"
            return Decision(kind=kind, category=category, language=language, matched=matched)

    return Decision(kind="proceed", category=None, language=language, matched=())
