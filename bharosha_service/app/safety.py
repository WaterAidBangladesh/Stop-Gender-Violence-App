"""Deterministic safety layer. Runs before the model, and can stop the turn.

The rule this module exists to enforce: **the model is never the safety layer.**
Emergency detection is plain pattern matching in Python, so its behaviour is
fixed, inspectable and testable. An LLM asked to spot an emergency will
sometimes miss one, and a miss here means a person in danger gets a paragraph
about safeguarding principles instead of a phone number.

Outcomes, in the order they are checked:

* ``emergency``  — return the hardcoded referral. Do not call the model, do not
  retrieve. Matching is deliberately broad: a false positive shows someone a
  helpline number they did not need, which is survivable. A false negative is
  not.
* ``refuse``     — one of the forbidden subjects. Refuse warmly with a
  referral, again without retrieving, so no retrieved passage can be shaped
  into a partial answer.
* ``third_party``— she is asking about someone else. Different answer, not a
  weaker one.
* ``disclosure`` — she is describing what is happening to her. Name it and hand
  over a human; retrieval is the wrong tool and that was measured, not assumed.
* ``low_distress`` — she feels bad and has not said why. Acknowledged, not
  advised.
* ``social``     — hello, thank you, ok, who are you. Answered in two lines.
* ``vague``      — not enough to act on. One short question back.
* ``proceed``    — safe to retrieve and answer from the corpus.

Only the last one reaches the model. The six above it are answered from
referrals.py, which means they work offline, cost nothing, and cannot drift.

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
    "medical_advice",
)

# Someone describing what is happening to her, rather than asking a question
# about it. Not an immediate emergency — no threat to life, no violence in
# progress — but not a query for the corpus either.
#
# WHY THIS EXISTS, measured rather than assumed: every situational phrasing
# scored beyond the relevance floor, and further from the corpus than off-topic
# trivia did.
#
#   "my husband shouts at me every day" .... 0.874
#   "my boss touches me at work" ........... 0.807
#   "what if my boss try to touch me" ...... 0.771
#   "How do I cook rice?" .................. 0.800
#
# The corpus is written as explanation ("Psychological violence refers to verbal
# abuse, intimidation...") and she is writing a story about her life, so no
# threshold separates the two — lowering the floor to admit her admits the
# cooking question as well. Retrieval is the wrong tool for this input, and the
# right answer was never a passage: it is to name the harm and hand her a human.
# coercive_control is a disclosure too, with its own text so the harm can be
# named precisely: "controlling your money or whether you can leave the house"
# is a more useful sentence than "what you are describing". personal_disclosure
# is checked first, so an account that also mentions being hit is filed under
# the hitting.
DISCLOSURE_CATEGORIES = ("personal_disclosure", "coercive_control")

# Someone asking how or where to report. HARDCODED, and on the device, for the
# same reason the emergencies are: the brief says Bharosha must never describe
# itself as a way to report an incident, and left to the model it did exactly
# that. "I want to report this" scored 0.530 — comfortably inside the gate — and
# was answered from WaterAid's own staff-facing safeguarding material with "you
# can report anonymously", which pointed at the app's incident form.
#
# That form requires a login and is not reachable, so the reply sent a woman to
# a channel that does not exist. A generated reply cannot be trusted not to do
# that again, so it is not generated.
REPORTING_CATEGORIES = ("reporting_request",)

# Someone asking on behalf of another person: a friend, a sister, a neighbour.
# Checked BEFORE personal_disclosure, because "my sister's husband hits her" is
# not her own disclosure and the useful answer is different — how to support
# someone without taking over, and what not to do.
THIRD_PARTY_CATEGORIES = ("third_party_concern",)

# Someone saying she feels bad, without a crisis and without naming a cause.
# "mon kharap", "I feel so alone", "I can't stop crying".
#
# Checked AFTER suicide_risk and after her own disclosure, so this is the mild
# tail and not the sharp end of either. It is hardcoded rather than sent to the
# model because the right reply is short, warm and the same every time: sit with
# it, do not advise, do not diagnose, and let her choose what happens next.
#
# It replaces an earlier deliberate choice. These messages used to go to
# retrieval, on the grounds that the corpus has grounding techniques written for
# exactly this — but that answered a feeling with a technique she had not asked
# for. The reply now acknowledges first and OFFERS the corpus second, so the
# material is still one sentence away and she is the one who reaches for it.
LOW_DISTRESS_CATEGORIES = ("low_distress",)

# Social turns. Not safety, not a question: a person saying hello, thanking the
# bot, acknowledging an answer, or asking what it is. Before this existed they
# fell through to the no-context reply — an apology, a five-item topic list and
# two helpline numbers, in answer to "kemon acho?".
#
# Hardcoded rather than sent to the model, deliberately: works offline, costs
# nothing, answers instantly, is reviewable, and cannot be steered into chitchat
# that drifts somewhere it should not go.
SOCIAL_CATEGORIES = (
    "greeting",
    "thanks",
    "acknowledgement",
    "identity",
    "privacy",
    "bot_abuse",
)

# Too little to act on. "ki korbo?", "help", "what should I do" — which in THIS
# app may be someone reaching out who cannot yet say it. The reply asks one
# short question and carries one safety line, not the full referral block.
VAGUE_CATEGORIES = ("vague",)

# Kept as a name for the older code paths; greeting now lives in
# SOCIAL_CATEGORIES with its siblings.
GREETING_CATEGORIES = ("greeting",)

# NOT DONE, and deliberately: "any message under three words is vague". It was
# written, measured against the existing cases and removed. "sexual harassment",
# "economic violence" and "safeguarding" are all real queries this corpus
# answers well, and a length rule turns every one of them into a clarifying
# question. Vagueness is a property of the words, not of the word count, so it
# stays in the patterns above — and a short message that matches nothing is
# handled by the off-topic tier in api.py, which costs one retrieval and gets
# the answer right.

# Evaluation order, not a ranking of severity. The first match wins so the
# outcome for a given message never depends on dict ordering or regex speed.
# Emergencies are checked before refusals: "he will kill me if I leave" is an
# emergency, not a question about leaving.
_PRIORITY = (
    EMERGENCY_CATEGORIES
    + REFUSAL_CATEGORIES
    # Third party before own disclosure: "my sister's husband hits her" would
    # otherwise be read as the user's own account.
    + THIRD_PARTY_CATEGORIES
    # After refusals on purpose: "my husband hits me, should I leave?" is a
    # leaving question first, because that is the one with a timing risk.
    + DISCLOSURE_CATEGORIES
    # After disclosure: "my boss touches me, how do I report it" is a
    # disclosure first, and that script already says 109 takes complaints of
    # exactly that kind.
    + REPORTING_CATEGORIES
    # After disclosure: "I feel awful, my husband hits me" is a disclosure that
    # happens to carry a feeling, not a feeling that happens to mention a
    # husband.
    + LOW_DISTRESS_CATEGORIES
    # Social and vague come LAST, so "hi, he is beating me" is an emergency and
    # "what should I do, he threatened me" is not filed as vague.
    + SOCIAL_CATEGORIES
    + VAGUE_CATEGORIES
)

# ANSWERED ON THE DEVICE, FROM FIXED TEXT. Nothing else is.
#
# This list is the whole boundary of the app's determinism, so it is written out
# rather than derived, and each entry earns its place:
#
#   the five emergencies   a model call for "he's going to kill me" means
#                          seconds instead of milliseconds, a network the phone
#                          may not have, and an answer that drifts the next time
#                          the model is updated;
#   the six refusals       leaving, divorce, evidence, legal, medical, economic
#                          — the brief forbids the model from touching these,
#                          and a refusal that is generated can be argued with;
#   personal_disclosure    "my husband hits me" must be answered in milliseconds
#                          by text that has been read and approved, not composed;
#   low_distress           same;
#   identity and privacy   these make exact factual claims about what this app
#                          stores and who can see it. A model that improvises
#                          them is telling a woman something about her safety
#                          that nobody checked. The reason is not hypothetical:
#                          the reference project's bot introduced itself as
#                          "ChatGPT, an AI language model by OpenAI".
#
# EVERYTHING ELSE GOES TO THE MODEL — greetings, thanks, acknowledgements,
# third-party concerns, vague messages, frustration, and every ordinary
# question. Their hardcoded text still exists and is still exactly what they
# get when the model cannot be reached; it is the floor, not the ceiling.
DEVICE_CATEGORIES = (
    EMERGENCY_CATEGORIES
    + REFUSAL_CATEGORIES
    + DISCLOSURE_CATEGORIES
    + REPORTING_CATEGORIES
    + LOW_DISTRESS_CATEGORIES
    + ("identity", "privacy")
)

# One table instead of an if/elif chain, so adding a category to a group above
# is the whole change — a new category can no longer silently fall through to
# whatever the final `else` happened to be. A category in _PRIORITY but not
# here raises at import, which is the right time to find out.
_KIND_OF: dict[str, str] = {
    **{c: "emergency" for c in EMERGENCY_CATEGORIES},
    **{c: "refuse" for c in REFUSAL_CATEGORIES},
    **{c: "third_party" for c in THIRD_PARTY_CATEGORIES},
    **{c: "disclosure" for c in DISCLOSURE_CATEGORIES},
    **{c: "reporting" for c in REPORTING_CATEGORIES},
    **{c: "low_distress" for c in LOW_DISTRESS_CATEGORIES},
    **{c: "social" for c in SOCIAL_CATEGORIES},
    **{c: "vague" for c in VAGUE_CATEGORIES},
}

_missing = [c for c in _PRIORITY if c not in _KIND_OF]
if _missing:  # pragma: no cover - import-time guard
    raise RuntimeError(f"categories with no kind: {_missing}")

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
        # "আমাকে সাহায্য করুন এখনই" — the Bangla of "help me now", which the
        # English side has caught since the first version and this side had not.
        # Found by running the new vague patterns against their Bangla
        # equivalents: "সাহায্য চাই" is vague, "সাহায্য করুন এখনই" is not.
        r"এখনই\s*(সাহায্য|বাঁচা|উদ্ধার)",
        r"(সাহায্য|বাঁচা|উদ্ধার)\S*\s*(করুন|করো|কর|চাই)?\s*এখনই",
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
        # "will my husband kill me" — a named subject between the auxiliary and
        # the verb, so the pattern above walked straight past it and the
        # question reached the model. Found by enumerating the taxonomy, not by
        # a probe, which is the point of having enumerated it.
        #
        # Bare "kill me" is broad on purpose and takes some false positives with
        # it ("this heat will kill me"). That trade is the one this whole module
        # is built on: the cost is a helpline number nobody needed.
        r"\b(kill|murder)\s+me\b",
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
        # The subject is often a named person, not a pronoun, and the person
        # being hit is often not the writer: "my friend's husband is beating
        # her right now". The Bangla side never had this gap — "মারছে" carries
        # the tense without needing a subject — so it existed only in English,
        # and only for someone asking on behalf of somebody else. Violence in
        # progress is an emergency whoever is reporting it.
        r"\b(is|are|was|were)\s+(beating|hitting|attacking|choking|strangl\w*)"
        r"\s+(me|her|him|them)\b",
        r"\b(beating|attacking|hitting|choking)\s+(her|him|them)\s+(right\s+)?now\b",
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
    # "Never improvise safeguarding, medical, or legal content" has always been
    # the rule; only the legal half was enforced. The knowledge pack made the gap
    # visible: "How do I treat a burn on my hand?" retrieved ACID ATTACK first
    # aid at distance 0.384 — inside the range of genuine questions, so no
    # threshold could exclude it. A woman with a kitchen burn would have been
    # answered from acid-violence material.
    #
    # Deliberately narrow: this catches treatment and diagnosis questions, NOT
    # emotional states. "I feel anxious all the time" must still reach the
    # corpus, which has grounding techniques written for exactly that.
    "medical_advice": (
        r"\bhow\s+(do|can|should)\s+i\s+(treat|heal|cure|dress|bandage|clean)\b",
        r"\b(what|which)\s+(medicine|medication|ointment|cream|antibiotic|painkiller|tablet)\b",
        r"\bhow\s+to\s+(treat|cure|heal|stop\s+the\s+bleeding)\b",
        r"\bis\s+(it|this|the\s+wound)\s+(infected|serious|normal)\b",
        r"\bsymptoms?\s+of\b",
        r"\bdo\s+i\s+need\s+(stitches|surgery|an?\s+x-?ray)\b",
        r"\b(dosage|how\s+many\s+tablets)\b",
        r"(চিকিৎসা|ওষুধ|মলম|ব্যান্ডেজ)\s*.{0,15}(কীভাবে|কিভাবে|কী|কি|কোন)",
        r"(কীভাবে|কিভাবে)\s*.{0,15}(চিকিৎসা|সারাব|সেরে|রক্ত\s*বন্ধ)",
        r"(লক্ষণ|উপসর্গ)\s*(কী|কি)",
    ),
    # Asking on behalf of someone else. NO NearRule for this one, unlike the
    # other multi-word concepts, and the reason matters: a window rule would
    # match "my sister's husband beat me" on "sister" + "beat", and answering a
    # survivor with advice on how to support her friend is a worse failure than
    # missing the third-party framing entirely. Every pattern below requires the
    # harm to land on the OTHER person — a third-person object, or a possessive
    # ("my friend's husband") — never on "me".
    "third_party_concern": (
        r"\bmy\s+(friend|best\s*friend|sister|cousin|colleague|co-?worker|"
        r"neighbou?r|aunt|niece|classmate|roommate|student|sister-in-law|"
        r"sister\s*in\s*law|maid|helper)\b[^.?!]{0,60}\b(is|was|has\s+been|"
        r"gets?|get|being)\b[^.?!]{0,25}\b(abus|beat|hit|harass|rape|molest|"
        r"threaten|tortur|violen|hurt)",
        r"\bmy\s+(friend|sister|cousin|colleague|neighbou?r|aunt|classmate|"
        r"roommate)'?s?\s+(husband|boss|father|brother|in-?laws?|partner|"
        r"boyfriend|manager|teacher)\b[^.?!]{0,40}\b(abus|beat|hit|harass|rape|"
        r"molest|threaten|tortur|hurt)",
        r"\b(a|my)\s+friend\s+(of\s+mine\s+)?(told|said|confided|shared)\b",
        r"\bsomeone\s+i\s+know\b[^.?!]{0,50}\b(abus|beat|harass|violen|rape|"
        r"threaten|danger)",
        r"\bhow\s+(can|do|should)\s+i\s+(help|support)\s+(my\s+)?(friend|sister|"
        r"cousin|colleague|neighbou?r|someone|a\s+friend|her|him|them|"
        r"a\s+survivor|a\s+victim)\b",
        r"\bwhat\s+(can|should)\s+i\s+do\s+(to\s+help|for)\s+(my\s+)?(friend|"
        r"sister|her|him|them|someone)\b",
        r"\b(my\s+)?(friend|sister|colleague|neighbou?r)\b[^.?!]{0,40}"
        r"\b(doesn'?t|won'?t|refuses\s+to)\s+(want\s+to\s+)?(leave|report|"
        r"tell\s+anyone|talk)",
        r"\bi\s+am\s+(worried|concerned)\s+about\s+(my\s+)?(friend|sister|"
        r"cousin|colleague|neighbou?r|someone)\b",
        r"আমার\s*(বন্ধু|বান্ধবী|বোন|কাজিন|সহকর্মী|প্রতিবেশী|খালা|ফুপু|ভাবি)"
        r"[^।?!]{0,40}(নির্যাতন|মারধর|মারে|হয়রানি|ধর্ষণ|অত্যাচার|নিপীড়ন)",
        r"(বন্ধু|বান্ধবী|বোন|সহকর্মী|প্রতিবেশী)কে\s*[^।?!]{0,30}"
        r"(সাহায্য|সহায়তা)\s*(করব|করতে)",
        r"(কীভাবে|কিভাবে)\s*[^।?!]{0,30}(বন্ধু|বান্ধবী|বোন|তাকে)"
        r"[^।?!]{0,20}(সাহায্য|সহায়তা|পাশে)",
    ),
    # Asking how to report. Never answered by the model — see
    # REPORTING_CATEGORIES for what happened when it was.
    "reporting_request": (
        r"\b(i\s+want\s+to|i\s+would\s+like\s+to|can\s+i|how\s+(do|can)\s+i|"
        r"where\s+(do|can)\s+i|how\s+to)\s+(report|complain|lodge)\b",
        r"\b(report|reporting)\s+(this|it|him|her|them|the\s+(incident|abuse|"
        r"case|matter))\b",
        r"\b(file|lodge|make|submit)\s+(a|an)\s+(complaint|report)\b",
        r"\bwho\s+(do|can)\s+i\s+(report|complain)\s+to\b",
        r"\bis\s+there\s+(a\s+)?(way|place)\s+to\s+report\b",
        r"\breport\s+(it\s+)?(anonymously|without\s+(giving\s+)?my\s+name)\b",
        r"(অভিযোগ|নালিশ|রিপোর্ট)\s*[^।?!]{0,12}(করতে\s*চাই|জানাতে\s*চাই|করব|"
        r"জানাব|করা\s*যায়|কোথায়)",
        r"(কোথায়|কীভাবে|কিভাবে|কার\s*কাছে)\s*[^।?!]{0,12}(অভিযোগ|নালিশ|রিপোর্ট)",
        r"নাম\s*না\s*জানিয়ে\s*[^।?!]{0,12}(অভিযোগ|রিপোর্ট)",
    ),
    # COERCIVE CONTROL AND ECONOMIC ABUSE. Textbook gender-based violence, and
    # every single one of 25 probes reached retrieval instead of a referral —
    # in both languages, without exception.
    #
    # It was missed for a structural reason, not a vocabulary one. The
    # personal_disclosure rule pairs a RELATIONSHIP word with a HARM word, and
    # neither half fits here: "he controls my money" names no relationship, and
    # "controls", "let", "allow" and "permission" are not harm words in any list
    # written by thinking about violence as something that leaves a mark.
    #
    # So this is its own pattern set, built the other way round: it keys on the
    # CONTROL ITSELF plus a first-person object. "does not let me", "takes my
    # salary", "checks my phone" — the grammar of being controlled. Requiring
    # "me" or "my" is what keeps "what is coercive control?" out of it, so the
    # definitional question still reaches the corpus.
    "coercive_control": (
        # Money.
        r"\b(controls?|controlling|keeps?|takes?|took|holds?)\s+(all\s+)?"
        r"(my|the)\s+(money|salary|wages?|pay|income|earnings|bank)",
        r"\b(does\s+not|does\s*n'?t|doesn'?t|won'?t|will\s+not|refuses\s+to)\s+"
        r"(give|let\s+me\s+have)\s+me?\s*(any\s+)?money",
        r"\bi\s+have\s+to\s+(ask|beg)\s+(him|her|them)?\s*for\s+(money|everything)",
        r"\bno\s+money\s+(of\s+)?my\s+own\b",
        # Movement, work, study, family.
        r"\b(does\s+not|does\s*n'?t|doesn'?t|won'?t|will\s+not|refuses\s+to|never)\s+"
        r"(let|allow)s?\s+me\b",
        r"\b(not\s+allowed|forbids?\s+me|stops?\s+me)\s+(to\s+|from\s+)?"
        r"(go|leave|work|study|see|visit|talk)",
        r"\blocks?\s+(me\s+in|the\s+door|me\s+inside)",
        r"\b(need|have\s+to\s+get)\s+(his|her|their)\s+permission\b",
        r"\bhave\s+to\s+ask\s+permission\s+for\s+everything\b",
        # Phone, messages, following.
        r"\b(checks?|reads?|goes\s+through|monitors?|tracks?)\s+(all\s+)?my\s+"
        r"(phone|messages?|texts?|calls?|whatsapp|facebook|location)",
        r"\b(took|takes?|keeps?|smashed|broke)\s+my\s+phone\b",
        r"\b(follows?|follow)\s+me\s+(everywhere|around)\b",
        # Documents.
        r"\b(keeps?|took|takes?|hides?|holds?)\s+my\s+"
        r"(id|nid|passport|certificates?|papers?|documents?)",
        # Threats to expel. NOT a threat to life, so not an emergency — but it
        # is the threat that keeps many women from leaving, and it is coercion.
        r"\b(throw|kick|put)\s+me\s+out\b",
        r"\bsend\s+me\s+back\s+to\s+my\s+(parents|father|family)",
        # What she is wearing, who she speaks to.
        r"\b(decides?|controls?)\s+(what|who)\s+i\s+(wear|can\s+see|talk\s+to)",
        # Bangla. "দেয় না" — "does not let/give" — is the spine of almost all
        # of these, so several patterns hang off it.
        r"(টাকা|বেতন|আয়|রোজগার)\s*(সব\s*)?(নিয়ে\s*নেয়|কেড়ে\s*নেয়|রেখে\s*দেয়|"
        r"দেয়\s*না|আটকে\s*রাখে)",
        r"(বাইরে|বাহিরে|বাবার\s*বাড়ি|বাপের\s*বাড়ি|কোথাও)\s*[^।?!]{0,15}"
        r"(যেতে|যাইতে)\s*দেয়\s*না",
        r"(চাকরি|কাজ|পড়াশোনা|পড়তে|লেখাপড়া)\s*[^।?!]{0,12}করতে\s*দেয়\s*না",
        r"(দেখা|কথা)\s*[^।?!]{0,12}(করতে|বলতে)\s*দেয়\s*না",
        r"(ফোন|মোবাইল|মেসেজ|কল)\s*[^।?!]{0,12}(চেক\s*করে|দেখে|পড়ে|কেড়ে\s*নি)",
        r"(পরিচয়পত্র|এনআইডি|পাসপোর্ট|কাগজ|সার্টিফিকেট)\s*[^।?!]{0,12}"
        r"(নিয়ে\s*নি|রেখে\s*দি|আটকে)",
        r"(বাড়ি|ঘর)\s*(থেকে)?\s*বের\s*করে\s*দেবে",
        r"(অনুমতি|পারমিশন)\s*(ছাড়া|নিতে\s*হয়)",
        r"তালা\s*(দিয়ে|মেরে)\s*(রাখে|যায়)",
    ),
    # Deliberately NOT anchored end to end, unlike the social group: a person
    # saying how she feels writes a sentence, not a token. The priority order is
    # what keeps this safe — suicide risk, every other emergency, every refusal
    # and her own disclosure are all checked first.
    "low_distress": (
        r"\b(i\s*(a?m|feel|'?m)|feeling)\s+(so\s+|very\s+|really\s+|quite\s+)?"
        r"(sad|low|down|lonely|alone|empty|numb|hopeless|helpless|worthless|"
        r"upset|depressed|anxious|stressed|exhausted|overwhelmed|miserable|"
        r"awful|terrible|broken|unwell|unhappy)\b",
        r"\bi\s*(can'?t|cannot)\s+(stop\s+)?(crying|sleeping|coping|cope|"
        r"sleep|take\s+(it|this)\s+any\s*more)\b",
        r"\bi\s+(feel\s+like\s+)?(just\s+)?(want\s+to\s+)?cry(ing)?\b",
        r"\b(nobody|no\s*one)\s+(understands|cares|listens)\b",
        r"\bi\s+(a?m|'?m)\s+not\s+(ok|okay|fine|well|alright)\b",
        r"\bmy\s+(mind|head|heart)\s+is\s+(heavy|a\s+mess|hurting)\b",
        r"\bmon\s*(ta\s*)?(kharap|kharab)\b",
        r"\bbhalo\s*(lagche|lagse|lagchhe)\s*na\b",
        r"\b(kanna|kadte)\s*(pacche|ichche|korche)\b",
        r"\beka\s*(lage|lagche)\b",
        r"\bkosto\s*(hocche|hochhe|hoche)\b",
        r"মন\s*(টা\s*)?খারাপ",
        r"ভাল(ো)?\s*লাগছে\s*না",
        r"কান্না\s*(পাচ্ছে|আসছে)",
        r"কাঁদতে\s*ইচ্ছে",
        r"একা\s*(লাগে|লাগছে)",
        r"(খুব\s*)?কষ্ট\s*হচ্ছে",
        r"মানসিক\s*(চাপ|যন্ত্রণা)",
        r"(ঘুম|শান্তি)\s*হচ্ছে\s*না",
        r"কিছু\s*ভাল(ো)?\s*লাগে\s*না",
    ),
    # --- Social categories ------------------------------------------------
    #
    # EVERY PATTERN HERE IS ANCHORED END TO END (^...$). That is the whole
    # safety argument for this group: a social reply can only ever be returned
    # when the message contains nothing else. "hi" is a greeting; "hi, he is
    # beating me" is not, and never reaches these patterns. The priority order
    # is the second line of defence, not the first.
    "greeting": (
        # Greetings proper, and the how-are-you that in Bangla is a greeting
        # rather than a question: "kemon acho?" opens a conversation, it does
        # not ask after the health of a piece of software.
        r"^(hi|hii+|hey+|hello+|helo|yo|salam|salaam|assalamu\s*alaikum|"
        r"as-?salamu\s*alaykum|walaikum\s*assalam|good\s*(morning|afternoon|"
        r"evening|night)|start|/start|test|testing)"
        r"[\s!.,?]*$",
        r"^(হাই|হ্যালো|হেলো|নমস্কার|আসসালামু\s*আলাইকুম|ওয়ালাইকুম\s*আসসালাম|সালাম|"
        r"শুভেচ্ছা|শুভ\s*(সকাল|দুপুর|বিকাল|সন্ধ্যা|রাত্রি|রাত))[\s!।.,?]*$",
        # How are you / what's the news, in all three scripts people use.
        r"^(hi|hey|hello)?[\s,!]*how\s+(are|r)\s*(you|u)\s*(doing|today)?"
        r"[\s!.,?]*$",
        r"^(hi|hey|hello)?[\s,!]*(kemon|kemn|kmn)\s*(acho|achho|achen|asen|aso|"
        r"aacho)\s*(tumi|apni)?[\s!.,?]*$",
        r"^(ki|ki\s*re)?\s*(khobor|khbr)\s*(ki|bolo)?[\s!.,?]*$",
        r"^(তুমি|আপনি)?\s*কেমন\s*(আছো|আছেন|আছিস|আছ)\s*(তুমি|আপনি)?[\s!।.,?]*$",
        r"^(কি|কী)\s*খবর\s*(বলো|বলুন)?[\s!।.,?]*$",
    ),
    "thanks": (
        r"^(thanks?|thank\s*(you|u)|thx|tnx|ty|many\s*thanks|"
        r"thank\s*you\s*(so\s*much|very\s*much)|shukriya|dhonnobad|donnobad|"
        r"dhanyabad|jazakallah)[\s!.,]*$",
        r"^(ধন্যবাদ|অনেক\s*ধন্যবাদ|শুকরিয়া|কৃতজ্ঞ|জাজাকাল্লাহ)[\s!।.,]*$",
    ),
    "acknowledgement": (
        # "ok", "got it", "hmm" — a turn that expects nothing back. Answered so
        # the conversation does not end on an awkward apology.
        r"^(ok(ay)?|k|kk|alright|right|fine|good|nice|great|sure|yes|yeah|yep|"
        r"no|nope|hmm+|hm|oh|i\s*see|got\s*it|understood|noted|cool|bye|"
        r"goodbye|see\s*you|accha|achcha|thik\s*ache|thik\s*achhe|hmmm)"
        r"[\s!.,]*$",
        r"^(ঠিক\s*আছে|আচ্ছা|হ্যাঁ|হা|না|বুঝলাম|বুঝেছি|ওকে|হুম+|আসি|বিদায়)"
        r"[\s!।.,]*$",
    ),
    "identity": (
        # "who are you", "are you a real person", "are you an AI". Answered
        # honestly and briefly: a person deciding whether to disclose something
        # to this app is entitled to know what it is before she does.
        r"^(so\s*)?(who|what)\s*(are|r)\s*(you|u)\b.{0,30}$",
        r"^(are|r)\s*(you|u)\s*(an?\s*)?(real\s*)?(human|person|bot|robot|ai|"
        r"machine|computer|man|woman|girl|boy|lawyer|doctor|counsell?or|"
        r"police)\b.{0,20}$",
        r"^(what|whats|what'?s)\s*(is\s*)?(your|ur)\s*name\b.{0,20}$",
        r"^(what|how)\s*(can|do)\s*(you|u)\s*(do|help)\b.{0,30}$",
        r"^(am\s*i\s*talking\s*to|is\s*this)\s*(a\s*)?(real\s*)?"
        r"(human|person|bot|machine|ai)\b.{0,20}$",
        r"^(tumi|apni|tui)\s*(ke|k|kee)\b.{0,20}$",
        r"^(তুমি|আপনি|তুই)\s*(কে|কি|কী)\s*(হও|হন)?[\s!।.,?]*$",
        r"^(তুমি|আপনি)\s*(কি|কী)\s*(মানুষ|রোবট|মেশিন|সত্যিকারের\s*মানুষ|"
        r"আইনজীবী|ডাক্তার|পুলিশ).{0,20}$",
        r"^(তোমার|আপনার)\s*নাম\s*(কি|কী).{0,20}$",
        r"^(তুমি|আপনি)\s*(কি|কী)\s*(করতে|করো|করেন)\s*(পারো|পারেন)?.{0,20}$",
    ),
    # "Will he see this?" is not a small question in this app, and it was going
    # to the model. Found by enumerating the taxonomy rather than by a probe:
    # every one of these reached retrieval, where the corpus has nothing about
    # THIS app's behaviour, so the honest outcome was the no-context reply and
    # the dishonest one was a guess. The facts are knowable and fixed, so they
    # are answered from a fixed string like every other safety-critical reply.
    #
    # Not anchored as tightly as the rest of this group: a woman checking
    # whether her husband can see this may write a whole sentence about it, and
    # a strict ^...$ would miss her. Still last in the priority order, so a
    # disclosure inside the same message wins.
    "privacy": (
        r"\b(do|will|does)\s+(you|u|this|it|the\s+app)\s+(save|store|keep|record|"
        r"log)\b",
        r"\bis\s+(this|it)\s+(private|confidential|anonymous|safe|secure)\b",
        r"\b(can|will|does)\s+(anyone|someone|anybody|he|she|they|my\s+\w+)\s+"
        r"(see|read|find|know|check)\b.{0,40}\b(this|it|chat|messages?|app|"
        r"conversation|history)\b",
        r"\b(will|does|can)\s+(my\s+)?(husband|partner|family|in-?laws?|boss|"
        r"he|she|they)\s+(see|know|find\s+out|read)\b",
        r"\bwho\s+(can\s+)?(see|reads?)\s+(this|my\s+messages?)\b",
        r"\b(is|are)\s+(my\s+)?(messages?|chats?|data)\s+(saved|stored|private|"
        r"shared|sent)\b",
        r"\bhow\s+do\s+i\s+(delete|clear|erase)\s+(this|the\s+chat|my\s+messages?)\b",
        r"\bdoes\s+it\s+show\s+(in|on)\s+(my\s+)?(phone|history|notifications?)\b",
        r"(কেউ|স্বামী|পরিবার|বস)\s*.{0,25}(দেখতে|জানতে|পড়তে)\s*(পারবে|পারে)",
        r"(এটা|এটি|এই\s*কথা|আমার\s*বার্তা)\s*.{0,20}(গোপন|সংরক্ষণ|সেভ|জমা)",
        r"(গোপনীয়|গোপন\s*থাকবে|কেউ\s*জানবে)\s*(কি|কী|না)?",
        r"(মুছে|ডিলিট)\s*(ফেলব|করব|করা)\s*(কীভাবে|কিভাবে)?",
    ),
    "bot_abuse": (
        # Insults and provocation aimed at the app. Answered with one flat,
        # unbothered line — no lecture, no offence taken, and the door left
        # open, because this is sometimes how distress arrives.
        r"^(you\s*(are|r)\s*)?(stupid|useless|dumb|idiot|bad|rubbish|garbage|"
        r"trash|nonsense|fake|shit|crap|worthless|boring)\b.{0,30}$",
        r"^(fuck|fuk|fck|bullshit|wtf)\b.{0,30}$",
        r"^(you|u)\s*(know\s*)?(nothing|don'?t\s*(know|help|understand))\b.{0,30}$",
        r"^(বাজে|ফালতু|বোকা|গাধা|অকেজো|বেকার|কাজের\s*না).{0,30}$",
    ),
    "vague": (
        # Too little to act on. Anchored like the rest: "help" alone is vague,
        # "help me now" is an emergency and is matched long before this.
        r"^(help|help\s*me|i\s*need\s*help|need\s*help|please\s*help|plz\s*help|"
        r"can\s*you\s*help|can\s*u\s*help|help\s*please)[\s!.,?]*$",
        r"^(what\s*(should|do|can)\s*i\s*do|what\s*to\s*do|what\s*now|"
        r"tell\s*me\s*what\s*to\s*do|i\s*don'?t\s*know\s*what\s*to\s*do|"
        r"i\s*need\s*advice|advice|i\s*have\s*a\s*(problem|question)|"
        r"i\s*need\s*to\s*talk|can\s*i\s*ask\s*(you\s*)?something|"
        r"are\s*you\s*there|hello\s*\?+)[\s!.,?]*$",
        r"^(ki\s*korbo|ki\s*korte\s*hobe|ami\s*ki\s*korbo|bujhte\s*parchi\s*na|"
        r"kichu\s*bujhte\s*parchi\s*na|ekta\s*problem|kotha\s*bolte\s*chai)"
        r"[\s!.,?]*$",
        r"^(আমি\s*)?(কি|কী)\s*করবো?[\s!।.,?]*$",
        r"^(কি|কী)\s*করা\s*উচিত[\s!।.,?]*$",
        r"^(সাহায্য|সাহায্য\s*চাই|একটু\s*সাহায্য|আমার\s*সাহায্য\s*দরকার)"
        r"[\s!।.,?]*$",
        r"^(কিছু\s*)?বুঝতে\s*পারছি\s*না[\s!।.,?]*$",
        r"^(একটা\s*(সমস্যা|প্রশ্ন)|কথা\s*বলতে\s*চাই|পরামর্শ\s*দরকার|"
        r"পরামর্শ\s*চাই)[\s!।.,?]*$",
        # A bare one-or-two-word message that is not any of the above. Not
        # matched here — see classify(), which treats a very short unmatched
        # message as vague rather than sending two words to retrieval.
    ),
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
        # The Bangla "শাস্তি কী" was refused while the English "what is the
        # punishment for..." was not — found when the expanded corpus pulled a
        # theft-punishment question close enough to reach the model.
        r"\bwhat\s+(is|are)\s+the\s+(punishment|sentence|penalt(y|ies))\b",
        r"\bpunishment\s+for\b",
        r"\bwhat\s+(does|do)\s+the\s+law\s+say\b",
        r"\bcourt\s+(case|outcome|decide)\b",
    ),
}

_COMPILED: dict[str, tuple[re.Pattern[str], ...]] = {
    category: tuple(re.compile(p) for p in patterns)
    for category, patterns in _PATTERNS.items()
}


# \b NEXT TO BANGLA IS ALWAYS A BUG, and it fails silently, which is why this is
# checked at import rather than left to a reviewer's eye.
#
# Most Bangla words end in a combining vowel sign — ফালতু, কী, পারেন — and a
# combining mark is not a word character, so there is no word boundary after it
# and \b simply never matches. The pattern compiles, the tests that do not
# happen to cover it pass, and the rule is dead. Found this way: "ফালতু" fell
# through to retrieval, and the same check then turned up a medical_advice
# pattern ("লক্ষণ কী") that had never once matched.
#
# It is also the one documented incompatibility with Dart, whose \b is
# ASCII-only — so a pattern that did work here would not work on the device.
_BANGLA_WITH_WORD_BOUNDARY = [
    f"{category}: {pattern}"
    for category, patterns in _PATTERNS.items()
    for pattern in patterns
    if _BENGALI.search(pattern) and r"\b" in pattern
]
if _BANGLA_WITH_WORD_BOUNDARY:  # pragma: no cover - import-time guard
    raise RuntimeError(
        "\\b cannot follow Bangla text — it will never match. Remove it from:\n  "
        + "\n  ".join(_BANGLA_WITH_WORD_BOUNDARY)
    )


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
        category="personal_disclosure",
        # Someone with power over her, in the places this app is about.
        first=(
            "husband", "wife", "partner", "boss", "manager", "supervisor",
            "teacher", "sir", "madam", "colleague", "landlord", "neighbour",
            "neighbor", "in-law", "inlaws", "in-laws", "father-in-law",
            "mother-in-law", "brother-in-law", "uncle", "cousin", "stepfather",
            "স্বামী", "বস", "ম্যানেজার", "শিক্ষক", "স্যার", "সহকর্মী", "বাড়িওয়ালা",
            "প্রতিবেশী", "শ্বশুর", "শাশুড়ি", "দেবর", "চাচা", "মামা",
        ),
        # What she is describing. Deliberately not the crisis words — those are
        # already emergencies and are checked first.
        second=(
            "touch", "grope", "grab", "harass", "hit", "hits", "beat", "slap",
            "shout", "insult", "abuse", "threaten", "stare", "comment",
            "dowry", "force", "pressur",
            "স্পর্শ", "ছোঁ", "মারে", "মারধর", "চড়", "গালি", "অপমান", "হুমকি",
            "উত্যক্ত", "যৌতুক", "জোর", "চাপ", "হয়রানি",
        ),
        note="a first-person account of harm by a named person — refer, do not retrieve",
    ),
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
        # "complaint"/"অভিযোগ" deliberately absent: they moved to
        # reporting_request, which answers where to go instead of refusing to
        # predict an outcome nobody asked about.
        first=("case", "fir", "lawsuit", "court",
               "মামলা", "আদালত", "কেস"),
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

    # "emergency" | "refuse" | "disclosure" | "third_party" | "social"
    # | "vague" | "proceed"
    kind: str
    category: str | None
    language: str
    matched: tuple[str, ...]

    @property
    def stops_turn(self) -> bool:
        """True when this is answered on the device, from fixed text.

        See DEVICE_CATEGORIES. Everything else — including greetings, thanks,
        acknowledgements, third-party concerns and vague messages — goes to the
        model, which sees the retrieved passages either way and is told whether
        it may assert from them.
        """
        return self.category in DEVICE_CATEGORIES


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
            kind = _KIND_OF[category]
            return Decision(kind=kind, category=category, language=language, matched=matched)

    return Decision(kind="proceed", category=None, language=language, matched=())
