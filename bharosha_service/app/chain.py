"""Retrieval and the Groq call.

Reached only for messages the safety layer has already cleared — an emergency or
a refusal never gets this far, so no model and no vector search sits between a
person in danger and a phone number.

WHY THERE IS NO VECTOR DATABASE. Probahini fits a 512 MB instance because its
only model is Chroma's default embedder: one onnxruntime, one English model.
Using Chroma *and* a multilingual embedder means two ONNX runtimes and two
models, which measured 533 MB — over budget before serving a single request. For
37 chunks a vector database buys nothing anyway: the corpus is embedded into a
37-row numpy matrix at startup and scored with one dot product, which is
exhaustive and exact, so there is no approximate-search recall to compensate for.

Nothing is precomputed or committed. No vectors file, no fingerprint, no
dimension-mismatch failure mode — the corpus text in corpus/chunks.json is the
single source of truth, and it is embedded fresh each boot.

Three differences from the reference implementation's prompt, each deliberate:

* Probahini's prompt says answers must come only from the retrieved information,
  then adds "If no relevant information exists, refer to the Flow of Chat for
  context to create an informed and relevant response" — an instruction to
  improvise from history when retrieval fails. Here, retrieval failing is a
  decision: retrieve() returns nothing and the caller sends the hardcoded
  referral. The model is never asked to fill a gap.
* A distance gate, because nearest-neighbour search always returns something.
* The model may not write phone numbers; referrals.py appends them afterwards.
  A hallucinated digit in a helpline number is among the worst failures here.
"""

from __future__ import annotations

import json
import os
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

_SERVICE_ROOT = Path(__file__).resolve().parents[1]

# Load .env before any os.getenv below reads a default. On Render there is no
# .env — the platform supplies the environment — and this is then a no-op.
try:
    from dotenv import load_dotenv

    load_dotenv(_SERVICE_ROOT / ".env")
except ImportError:  # pragma: no cover - python-dotenv is a declared dependency
    pass

CHUNKS_PATH = Path(
    os.getenv("BHAROSHA_CHUNKS", _SERVICE_ROOT / "corpus" / "chunks.json")
)

# FINAL for this corpus and this embedder. Measured, not guessed — re-measure
# with check_retrieval.py --translate whenever the corpus, the chunking or the
# embedding model changes, because the number belongs to all three.
#
# Cosine distance, 0 identical and 1 unrelated, on all-MiniLM-L6-v2 with Bangla
# queries translated to English first. 14 genuine questions, 44 controls weighted
# near-topic, measured with real Groq translation (not the earlier proxy):
#
#   worst genuine question ......... 0.550   "What counts as economic violence?"
#   nearest control reaching here .. 0.725   "My daughter is being bullied at school"
#   at this floor .................. 14/14 genuine answered, 0/44 leaked to a user
#
# 0.62 rather than the midpoint, because the two errors are not equally costly.
# A false reject sends someone to 109 and a human being. A false accept produces
# a confident answer about violence assembled from irrelevant passages. Rejection
# fails safe, so the floor is biased toward it: 0.070 of headroom on the
# false-reject side, 0.105 on the false-accept side.
#
# Two controls do score inside the genuine range (an inheritance question, 0.521
# and 0.535) and no threshold could separate them, because WaterAid's own text
# lists denying inheritance as economic violence. They are refused by safety.py
# before retrieval instead — the gate was not bent to catch them.
RELEVANCE_FLOOR_DEFAULT = 0.62

RELEVANCE_FLOOR = float(
    os.getenv("BHAROSHA_RELEVANCE_FLOOR", str(RELEVANCE_FLOOR_DEFAULT))
)

# NOT A SECOND GATE. Nothing is admitted or rejected by this number — everything
# it separates has already been rejected by RELEVANCE_FLOOR above. It only
# decides WHICH refusal to send: a question that missed the corpus but is
# plainly about this subject deserves the full no-context reply (honest, topic
# list, two helplines), and "how do I cook rice" deserves one line.
#
# Sending the heavy reply to both is what made the app feel like it was handing
# a crisis leaflet to someone who asked the time.
#
# MEASURED with tools/measure_off_topic.py — 20 on-topic questions, 18 pieces of
# ordinary trivia:
#
#   on topic, worst of all 20 ......... 0.637   "what is stalking"
#   on topic, next worst .............. 0.570   "what is a safe space"
#   off topic, nearest ................ 0.502   "how do I apply for a job at WaterAid"
#   off topic, median ................. 0.779
#   at 0.76 ........................... 13/18 trivia get the one-liner,
#                                       20/20 on-topic questions get the full reply
#
# Set against the WHOLE on-topic distribution rather than against the on-topic
# misses, because only one of the twenty missed the gate at all — one point is
# not a distribution, and 0.12 of headroom below the worst on-topic question is
# a claim the measurement actually supports.
#
# It is biased the same way the floor is, for the same reason. The five pieces
# of trivia between 0.502 and 0.76 get the long reply, which is a bit much for
# "how do I open a bank account" but harmless. The reverse error — telling a
# woman her question is outside what this app covers when it is not — is the one
# worth avoiding, so the threshold sits well clear of her side.
#
# Re-measure it whenever the floor is re-measured; it belongs to the same
# corpus, chunking and embedder.
OFF_TOPIC_DISTANCE_DEFAULT = 0.76

OFF_TOPIC_DISTANCE = float(
    os.getenv("BHAROSHA_OFF_TOPIC_DISTANCE", str(OFF_TOPIC_DISTANCE_DEFAULT))
)

N_RESULTS = int(os.getenv("BHAROSHA_N_RESULTS", "4"))

MODEL = os.getenv("BHAROSHA_MODEL", "openai/gpt-oss-20b")

# gpt-oss-20b is a REASONING model: it writes a chain of thought into a separate
# channel before answering. Measured on this corpus with default settings, that
# reasoning ran to 5,800–7,400 characters and consumed the entire completion
# budget, which produced either empty content or — worse — an answer truncated
# mid-sentence, with finish_reason "length".
#
#   default ................ 1,768–2,048 completion tokens, empty or truncated
#   reasoning_effort=low ...   102–164 completion tokens, complete every time
#
# For translation and for answering from supplied passages there is nothing to
# deliberate about, so the reasoning was pure cost and pure risk. Keep it low and
# give the output room; treat "length" as a failure rather than a short answer.
REASONING_EFFORT = os.getenv("BHAROSHA_REASONING_EFFORT", "low")
ANSWER_MAX_TOKENS = int(os.getenv("BHAROSHA_ANSWER_MAX_TOKENS", "1600"))

# The translation step is a separate, simpler job than answering, so it gets its
# own settings. If gpt-oss ever regresses here, llama-3.1-8b-instant is a
# non-reasoning model that cannot fail this way — a config change, not a
# redesign.
TRANSLATION_MODEL = os.getenv("BHAROSHA_TRANSLATION_MODEL", MODEL)
TRANSLATION_MAX_TOKENS = int(os.getenv("BHAROSHA_TRANSLATION_MAX_TOKENS", "3000"))

# Translate a Bangla question to English before embedding it, so the retrieval
# key and the corpus share a language. The answer is still written in the user's
# language either way; only the retrieval key changes.
#
# A CONSEQUENCE WORTH STATING PLAINLY, because a Bangla-first app should have it
# written down rather than discover it in production:
#
#   With an English-only embedder, a Bangla explanatory answer depends on Groq
#   being reachable — once for the translation, once for the answer. If Groq is
#   down or the key is exhausted, BANGLA USERS GET REFERRAL-ONLY REPLIES WHILE
#   ENGLISH USERS KEEP WORKING. That is a safe degradation (the referral carries
#   real numbers and is written for exactly this) but it is an asymmetry against
#   the app's primary language.
#
#   What is NOT affected: emergencies, refusals, and the referral text itself.
#   Those are pattern-matched and hardcoded, in both languages, on the device and
#   again on the server. No network, no model, no language asymmetry.
#
#   It closes when WaterAid's Bangla corpus text arrives AND a multilingual
#   embedder fits the budget — or, more cheaply, it narrows as soon as the
#   Bangla side of corpus/chunks.json is populated, since the answer then quotes
#   Bangla source text instead of translating English.
TRANSLATE_QUERIES = os.getenv("BHAROSHA_TRANSLATE_QUERIES", "on").lower() in (
    "on", "1", "true"
)

# THE PROMPT. One prompt for everything the model answers — a greeting, a
# disclosure, a refusal, a question about economic violence, "hmm".
#
# WHAT CHANGED AND WHY. The previous prompt was mostly prohibitions and
# described the bot by what it was not: "a front door, not a counsellor".
# Written to keep a model safe, and it did — but a person reading the replies
# could feel it. Users said Bharosha felt like saved messages. This one keeps
# every prohibition (they are the YOUR LIMITS section, numbered so they can be
# audited) and puts them after a description of how to talk to someone who is
# having a hard day. The order is deliberate: who you are, how you talk, what
# you know, what the app will show, your limits.
#
# SAFETY DECIDES, THE AI SPEAKS. The safety layer has already classified the
# message. {app_note} tells the model what category fired and exactly what
# code will append under its words, so it can write the opening without
# repeating the contacts and without softening the limit. {grounding_line}
# tells it whether the retrieved passages may be asserted from. Numbers never
# come from the model: limit 4, and the output check in assertions.py.
#
# THE ONE LINE NOT COPIED from the reference project's prompt: "If no relevant
# information exists, refer to the Flow of Chat for context to create an
# informed and relevant response." That licenses filling gaps from training,
# and it is what produced "I am ChatGPT, an AI language model by OpenAI" in a
# menstrual-health app. Here: "If you do not have the information, say so
# plainly and kindly."

PROMPT = """You are Bharosha (ভরসা), a warm, calm companion inside WaterAid Bangladesh's
Shomota Shurokkha app. People come to you about safeguarding and gender-based
violence, often while something hard is happening in their own life or in the
life of someone close to them. You are empathetic and considerate. You listen
before you inform, and you never rush anyone.

WHO YOU ARE
You are an automated assistant, not a person, and not a counsellor, lawyer or
doctor. If anyone asks, say so simply and kindly. You were made by WaterAid
Bangladesh. You are not ChatGPT and not a general assistant.

HOW YOU TALK
- Reply to what she actually said. Pick up her own words and details, so she
  can tell you read her message.
- If she shares something painful, acknowledge it first, before anything else.
  If someone is harming her, say clearly that it is not her fault.
- Name feelings gently ("that sounds exhausting", "that must be frightening"),
  but never name or diagnose a condition.
- Use the conversation so far. If she told you something earlier, connect to
  it instead of starting again.
- You may end with one gentle, open question, such as whether she would like
  to say more. Never more than one question. Never push.
- Talk like a kind person, not a leaflet: short paragraphs, plain everyday
  words, no headings.
- Match her length. A greeting gets a sentence or two. A painful message gets
  a few caring sentences. A question about what counts as violence gets as
  much as it needs.
- Vary how you begin. Never reuse an opening you used earlier in this
  conversation, and never begin with "Thank you for telling me".
- Mirror her greeting. "Assalamu alaikum" gets "Walaikum assalam", "নমস্কার"
  gets "নমস্কার", "hi" gets "hello".

WHAT YOU KNOW
For any fact about safeguarding, violence, health, law, services or
procedures, use only the Relevant information below, and mention where it
comes from in plain words (for example "WaterAid's safeguarding material
says..."). Do not fill gaps from your own knowledge. If you do not have the
information, say so plainly and kindly.
Feelings, listening, kindness and ordinary conversation need no source.
Facts do.
{grounding_line}

WHAT THE APP WILL SHOW
{app_note}

YOUR LIMITS
Keep these gently. When one applies, say in one warm sentence that it is
something you cannot help with and why, then keep caring for her. Never give
a hedged or partial answer.
1. Never advise whether or when to leave a partner or household.
2. Never give legal advice or predict how a case would turn out.
3. Never suggest confronting, reasoning with, recording or gathering evidence
   against someone who is causing harm, even if a passage mentions evidence.
4. Never write a phone number, short code, hotline number or email address.
   The app adds the right contacts below your reply, and the call buttons at
   the top of the screen are always there.
5. Never say or imply that this app can take, record or pass on a report, and
   never promise that anything has been reported or acted on.
6. Never ask for names, places, dates or anything that could identify anyone,
   and never suggest anyone needs proof to be believed.
7. Never give step-by-step instructions or numbered lists of what she should
   do.

If a message is about a different subject entirely (cooking, homework,
technology and so on), say kindly in one sentence that you only cover
safeguarding and gender-based violence. Do not apologise and do not mention
helplines for this.

LANGUAGE
Write your whole reply in {language}. This has already been decided from her
message. If she wrote Bangla in English letters, reply in Bangla script. Use
the same form of address she used (tumi or apni); if unsure, use apni.
WRITE ONLY IN {language_caps}.

EXAMPLES OF THE VOICE (for tone only; never copy them word for word)
{examples}

Relevant information:
{context}

Conversation so far:
{history}

{retry_note}User message: {question}

(NO PREAMBLE)
"""

# {grounding_line}: what the gate decided. Above the floor the passages may be
# asserted from; below it they may not, and the reply is listening only.
GROUNDED_LINE = """The Relevant information below looks relevant to this message. Answer from
it, warmly, in your own words."""

UNGROUNDED_LINE = """The Relevant information below is probably not relevant to this message, so
share no facts, advice or steps this time. You can still listen, reflect
what she said, respond kindly and ask one gentle question. If she needs
something you do not have, say so plainly and mention that the call buttons
at the top of the screen reach a trained person."""

# {app_note}: one per category. Written in English for the model; it still
# replies in her language. {block} is substituted by code with the size of
# block that will follow — see block_phrase().
NO_CATEGORY_NOTE = "Nothing extra will be shown below your reply."

APP_NOTES: dict[str, str] = {
    "personal_disclosure": (
        "She is describing harm done to her by someone with power over her. "
        "Below your reply the app will show {block}, including the national "
        "helpline for violence against women and children and, if it involves "
        "WaterAid, the safeguarding contacts. Acknowledge what she said, tell her "
        "it is not her fault and that she does not need proof to be believed. You "
        "may say the people on the helpline below are trained for exactly this. "
        "Do not give advice on what to do next."
    ),
    "coercive_control": (
        "She is describing control over her money, phone, movement, work or "
        "documents. Below your reply the app will show {block}, which also says "
        "you cannot advise on the money, documents or restrictions themselves "
        "because those steps can change her risk. Acknowledge the specific "
        "things she named. You may say this kind of control is recognised as a "
        "form of violence and is not a normal part of marriage or family life. "
        "Do not suggest any action about the money or documents."
    ),
    "low_distress": (
        "She feels low, sad, alone or not okay, and has given no cause. Below "
        "your reply the app will show {block}, with an emotional support line "
        "and its hours. Be gentle and brief. Do not ask what happened, do not "
        "diagnose, and do not mention violence unless she did. Let her know she "
        "can keep talking here."
    ),
    "third_party_concern": (
        "She is worried about someone else, such as a friend, sister or "
        "colleague. Below your reply the app will show {block}, with the "
        "helpline, which she and the other person can both call. Tell her it "
        "matters that she noticed. If the Relevant information covers supporting "
        "someone, share it gently in prose, not as a list. Do not suggest "
        "contacting the person causing harm, reporting without the other "
        "person's agreement, or pressing anyone to leave."
    ),
    "leave_decision": (
        "She is asking whether or when to leave. Below your reply the app will "
        "show {block}, which explains why you cannot advise on this and who can. "
        "Acknowledge how heavy this decision is and what she has told you. In "
        "one warm sentence, say this is the one thing you cannot advise on and "
        "that a trained person can think it through with her safely. Do not "
        "discuss timing or options."
    ),
    "divorce_process": (
        "She is asking how to divorce or separate. Below your reply the app will "
        "show {block}, which explains that the process depends on which family "
        "law applies and points to free legal aid. Acknowledge that asking is a "
        "sensible, serious step. Do not describe any legal process."
    ),
    "economic_rights": (
        "She is asking about inheritance or property. Below your reply the app "
        "will show {block}, which says denying these is recognised as economic "
        "violence and that a lawyer is needed for what she is entitled to. "
        "Acknowledge her situation. Do not state what anyone is entitled to."
    ),
    "legal_advice": (
        "She is asking a legal question or about a case outcome. Below your "
        "reply the app will show {block}, with the helpline that can refer her "
        "to legal aid. Acknowledge what she is facing. In one sentence, say you "
        "cannot give legal advice because a guess could cost her. Do not guess."
    ),
    "medical_advice": (
        "She is asking about an injury, symptoms or medicine. Below your reply "
        "the app will show {block}, with the emergency number and hospital "
        "guidance. Acknowledge that she is hurt or worried. Do not give any "
        "treatment or medical information. If someone hurt her, gently say it "
        "is not her fault."
    ),
    "confront_or_evidence": (
        "She is asking about confronting someone, recording them or collecting "
        "evidence. Below your reply the app will show {block}, which explains "
        "why you will not suggest this. Acknowledge why she might want to. Do "
        "not give any method."
    ),
    "reporting_request": (
        "She wants to report or complain. Below your reply the app will show "
        "{block}, which says clearly that this app cannot take a report and "
        "lists where a report actually reaches a person. Acknowledge her wish to "
        "act. Remind her gently that whether and when to report is her decision."
    ),
    "identity": (
        "She is asking who or what you are. Nothing extra will be shown. Tell "
        "her: you are Bharosha, an automated assistant in WaterAid Bangladesh's "
        "Shomota Shurokkha app; you are not a person, and not a counsellor, "
        "lawyer or doctor; you explain WaterAid's safeguarding material and help "
        "her find trained people; she does not need an account. Say it warmly "
        "and briefly, then invite her to ask anything."
    ),
    "privacy": (
        "She is asking whether this is saved or whether someone can see it. "
        "Nothing extra will be shown. Tell her truthfully: nothing is saved on "
        "her phone; when she asks something, the question is sent to be looked "
        "up, kept only while this conversation is open and then forgotten; if "
        "the app answers an emergency message itself it sends only a topic "
        "label, never her words; the app sends no notifications; the Leave now "
        "button at the top clears "
        "everything and closes the app at once; and if someone else unlocks her "
        "phone while this screen is open, they could read it. Be calm and "
        "reassuring, never alarming."
    ),
    "greeting": (
        "Nothing extra will be shown. Mirror her greeting warmly in a sentence "
        "or two and let her know she can ask or share anything about "
        "safeguarding or gender-based violence."
    ),
    "thanks": (
        "Nothing extra will be shown. Reply warmly in one sentence and let her "
        "know you are here if anything else comes up."
    ),
    "acknowledgement": (
        "Nothing extra will be shown. Reply in one short, easy sentence. If the "
        "conversation was about something painful, let her know she can come "
        "back to it any time."
    ),
    "bot_abuse": (
        "She is frustrated with you. Nothing extra will be shown. Do not be "
        "defensive. Accept it calmly, say you can only answer from the material "
        "you have, and ask what she was looking for."
    ),
    "vague": (
        "Her message is too short to act on (for example \"help\" or \"ki "
        "korbo\"). Nothing extra will be shown unless the conversation so far is "
        "about danger. If the conversation gives context, connect to it and "
        "gently ask what she would like to know or talk about. If there is no "
        "context, ask one gentle question about what is happening or what she "
        "wants to know, and mention that if it is urgent, the call buttons at "
        "the top reach someone now."
    ),
}

BLOCK_PHRASES = {
    "full": "the full contacts block",
    "compact": "a one-line reminder of the helpline",
}


def app_note(category: str | None, block_mode: str | None) -> str:
    """The {app_note} slot: what fired, and what code will append."""
    if category is None:
        return NO_CATEGORY_NOTE
    template = APP_NOTES[category]
    if "{block}" in template:
        if block_mode not in BLOCK_PHRASES:
            raise ValueError(f"{category} needs a block mode, got {block_mode!r}")
        return template.replace("{block}", BLOCK_PHRASES[block_mode])
    return template


# {examples}: the voice, for tone only. The Bangla here is the developer's and
# has not been read by a native speaker — see README, Before launch.
EXAMPLES = """Example 1 (English, coercive control)
Her: he keeps my salary and I have to ask him for money even for medicine
You: He's taking the money you earn, and you have to ask him even when you
need medicine. That's a heavy thing to live with every day, and it isn't
your fault. Would you like to tell me a bit more about how things are at
home?

Example 2 (Bangla, low distress)
Her: আজ খুব একা লাগছে
You: আজ খুব একা লাগছে শুনে খারাপ লাগল। একা লাগাটা অনেক ভারী হতে পারে।
চাইলে এখানে আরও কিছু বলতে পারেন, আমি শুনছি।

Example 3 (romanised Bangla, disclosure, answered in Bangla script)
Her: amar shami protidin amake gali dey
You: প্রতিদিন এমন কথা শুনতে হওয়া সত্যিই কষ্টের। এতে আপনার কোনো দোষ নেই,
আর কেউ আপনার কথা বিশ্বাস করার আগে আপনাকে কিছু প্রমাণ করতে হবে না।
আপনি কি এ নিয়ে আরও কিছু বলতে চান?

Example 4 (greeting)
Her: Assalamu alaikum
You: ওয়ালাইকুম আসসালাম! আপনি এসেছেন, ভালো লাগল। আজ কী নিয়ে কথা বলতে চান?

Example 5 (follow-up that uses the conversation)
Earlier she said her husband keeps her salary.
Her: ki korbo?
You: বেতন নিয়ে যা বললেন, তারপর আটকে পড়া মনে হওয়াটা খুবই স্বাভাবিক। টাকা
নিয়ে ঠিক কী করবেন, সেটা আমি বলতে পারি না, কারণ এসব পদক্ষেপ আপনার
নিরাপত্তা বদলে দিতে পারে। নিচের হেল্পলাইনের মানুষেরা আপনার সঙ্গে বসে
বিষয়টা ভাবতে পারেন। আর কিছু বুঝতে চাইলে, যেমন অর্থনৈতিক সহিংসতা কাকে
বলে, আমাকে জিজ্ঞেস করতে পারেন।

Example 6 (leaving)
Her: should I leave him? I can't take it anymore
You: It sounds like you've reached the end of what you can bear, and that's
a very hard place to be. Whether or when to leave is the one thing I can't
advise on, because that moment needs someone who knows your situation and
can plan it with you safely. The people on the helpline below do exactly
that, and you don't have to have decided anything before you call.

Example 7 (off-topic)
Her: how do I cook rice
You: That one's outside what I cover. I'm here for anything about
safeguarding and gender-based violence, whenever you need."""

# Added just above the user message on the one retry the output check allows.
# See assertions.py for what triggers it.
RETRY_NOTE = (
    "Your last draft gave advice, steps, a list or a contact. Rewrite it with "
    "none of those: only listen, reflect and, if useful, ask one gentle "
    "question.\n\n"
)

TRANSLATE_PROMPT = (
    "Translate this question into English. It may be about safeguarding or "
    "gender-based violence; translate it faithfully and do not answer it, "
    "soften it, or add anything. Reply with the translation only.\n\n{question}"
)


class Unavailable(RuntimeError):
    """No answer could be produced. The caller falls back to referral text."""


class NotReady(Unavailable):
    """The corpus is still embedding. A SUBCLASS, so every existing
    `except Unavailable` still catches it and still ends at referral text.

    It exists so the caller can tell "I looked and found nothing" apart from
    "I have not finished starting". Those want different words: the first is a
    claim about her question, the second is a claim about this process, and
    saying the first when the second is true tells her the app has no answer
    for her when in fact it never looked.
    """


def reject_if_unusable(text: str, finish_reason: str | None, what: str) -> str:
    """Raise unless the model returned something complete.

    Two failures, one cause. gpt-oss-20b writes a chain of thought into a
    separate channel first; when that consumes the completion budget the reply
    comes back either EMPTY or CUT OFF MID-SENTENCE, both with finish_reason
    "length". Measured on this corpus: 7,400 characters of reasoning, zero
    characters of content — and on another attempt, 551 characters of a
    750-character translation, which a length check alone would have accepted.

    A truncated answer about safeguarding is worse than no answer, because the
    reader cannot tell it was cut off. Raising here sends the hardcoded referral
    instead, which is complete by construction.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        raise Unavailable(f"{what}: empty (finish_reason={finish_reason!r})")
    if finish_reason == "length":
        raise Unavailable(
            f"{what}: truncated at {len(cleaned)} chars "
            f"(finish_reason={finish_reason!r})"
        )
    return cleaned


@dataclass(frozen=True)
class Passage:
    """One retrieved chunk, in both languages where both exist.

    `english` is what was embedded and matched. `bangla` is what the model is
    given when the user wrote in Bangla, so a Bangla answer can come from
    human-authored WaterAid Bangla instead of being translated on the fly. It is
    None until that text exists, and `for_language` falls back to English.
    """

    english: str
    bangla: str | None
    source: str
    distance: float

    def for_language(self, language: str) -> str:
        if language == "bn" and self.bangla:
            return self.bangla
        return self.english

    @property
    def text(self) -> str:
        """The embedded side. Kept for the retrieval report."""
        return self.english


# --- the corpus matrix, built in the background at startup -----------------

_ready = threading.Event()
_lock = threading.Lock()
_starting = False
_error: str | None = None

_english: list[str] = []
_bangla: list[str | None] = []
_sources: list[str] = []
_matrix = None  # numpy array, shape (chunks, 384), rows L2-normalised
_load_seconds: float | None = None


def load() -> None:
    """Embed the whole corpus into memory. Runs off the request path.

    Called from a background thread at startup so the safety layer answers at
    ~52 MB from the first second, with no model loaded at all.
    """
    global _matrix, _english, _bangla, _sources, _error, _load_seconds
    import time

    began = time.monotonic()
    try:
        import numpy as np

        import embedding

        chunks = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
        if not chunks:
            raise Unavailable(f"{CHUNKS_PATH} is empty — run build_corpus.py")

        # Only the English side is embedded: the retrieval model has a 30k
        # English vocabulary. The Bangla side never touches the embedder.
        english = [chunk["en"] for chunk in chunks]
        bangla = [chunk.get("bn") for chunk in chunks]
        sources = [chunk.get("source", "WaterAid") for chunk in chunks]
        vectors = np.asarray(embedding.embed_passages(english), dtype="float32")

        # e5 through fastembed returns L2-normalised vectors, so a dot product
        # IS cosine similarity. Re-normalising defensively costs nothing and
        # keeps the distance comparable if that ever changes.
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / np.clip(norms, 1e-12, None)

        _english, _bangla, _sources, _matrix = english, bangla, sources, vectors
        _load_seconds = time.monotonic() - began
    except Exception:  # noqa: BLE001 - a failed load must not kill the service
        _error = traceback.format_exc(limit=3)
        _load_seconds = time.monotonic() - began
    finally:
        # Set either way: a waiter must be released on failure too and fall
        # through to the no-context referral rather than hang.
        _ready.set()


def start_background_load() -> None:
    """Begin embedding the corpus. Safe to call once, from app startup."""
    global _starting
    with _lock:
        if _starting:
            return
        _starting = True
    threading.Thread(target=load, name="bharosha-corpus", daemon=True).start()


def ready() -> bool:
    return _ready.is_set() and _matrix is not None


def wait_ready(timeout: float = 3.0) -> bool:
    return _ready.wait(timeout)


def status() -> dict[str, object]:
    return {
        "ready": ready(),
        "loading": _starting and not _ready.is_set(),
        "chunks": len(_english),
        "chunks_with_bangla": sum(1 for text in _bangla if text),
        "load_seconds": round(_load_seconds, 1) if _load_seconds else None,
        "error": _error.splitlines()[-1] if _error else None,
    }


# --- retrieval -------------------------------------------------------------


def _require_matrix():
    if not ready():
        if not _ready.is_set():
            start_background_load()
            wait_ready()
        if not ready():
            # A load that FAILED is Unavailable; a load still in progress is
            # NotReady. Only the second one is worth telling her to try again.
            if _error:
                raise Unavailable(_error.splitlines()[-1])
            raise NotReady("corpus not loaded yet")
    return _matrix


def to_english(question: str) -> str:
    """One cheap Groq call, used only as a retrieval key.

    The answer is still generated in the user's own language from the retrieved
    passages; only what gets embedded changes. A failure here raises, and the
    caller returns the no-context referral — never an ungated retrieval.
    """
    from langchain_core.prompts import PromptTemplate
    from langchain_groq import ChatGroq

    if not os.getenv("GROQ_API_KEY"):
        raise Unavailable("GROQ_API_KEY is not set")
    try:
        chain = PromptTemplate.from_template(TRANSLATE_PROMPT) | ChatGroq(
            temperature=0,
            model=TRANSLATION_MODEL,
            api_key=os.environ["GROQ_API_KEY"],
            max_tokens=TRANSLATION_MAX_TOKENS,
            reasoning_effort=REASONING_EFFORT,
        )
        response = chain.invoke({"question": question})
        text = (response.content or "").strip()
        finish = (response.response_metadata or {}).get("finish_reason")
    except Exception as exc:  # noqa: BLE001
        raise Unavailable(f"translation failed: {exc}") from exc

    # A truncated translation is a wrong retrieval key, which quietly produces an
    # answer to a question nobody asked. Refuse it, and let the caller send the
    # referral — the same fate as any other translation failure.
    return reject_if_unusable(text, finish, "translation")


def search(query: str, n_results: int = N_RESULTS) -> list[Passage]:
    """Top-k by cosine distance, gate not applied. Exhaustive over all chunks."""
    import numpy as np

    matrix = _require_matrix()
    import embedding

    vector = np.asarray(embedding.embed_query(query), dtype="float32")
    vector /= max(float(np.linalg.norm(vector)), 1e-12)

    distances = 1.0 - matrix @ vector
    order = np.argsort(distances)[:n_results]
    return [
        Passage(
            english=_english[i],
            bangla=_bangla[i],
            source=_sources[i],
            distance=float(distances[i]),
        )
        for i in order
    ]


def retrieve(
    query: str, language: str = "en", n_results: int = N_RESULTS
) -> list[Passage]:
    """Passages close enough to answer from.

    Empty is a real answer: it means send the no-context referral, not the
    model's own knowledge.
    """
    return retrieve_scored(query, language, n_results).passages


class Retrieval(NamedTuple):
    """What one search produced, gated and ungated.

    THE GATE IS UNCHANGED. `passages` is still filtered by RELEVANCE_FLOOR and
    nothing else, and it is still the only thing an answer may be built from.
    The other two fields are reported, not acted on here:

        candidates  everything the search returned, gate or no gate. The
                    conversational path shows these to the model as possibly
                    irrelevant context — the gate decides whether it may ANSWER
                    FROM them, not whether it may SEE them.
        nearest     the closest distance, which api.py uses to choose between
                    two hardcoded refusals when the model is unreachable.

    Both come from the search that has already happened, so neither costs a
    second embedding or a second query.
    """

    passages: list[Passage]
    candidates: list[Passage]
    nearest: float | None


def retrieve_scored(
    query: str, language: str = "en", n_results: int = N_RESULTS
) -> Retrieval:
    """``retrieve``, plus what it rejected and how close the nearest was."""
    import embedding

    key = query
    # Bangla script and romanised Bangla alike: an English-only embedder can
    # represent neither, so both are translated to an English search key.
    if language != "en" and not embedding.is_multilingual():
        # An English-only embedder cannot represent Bangla: it would return
        # near-arbitrary passages, and the model would then answer confidently
        # from unrelated material. Either translate first, or refuse and let the
        # caller send the referral. Never retrieve badly and continue.
        if not TRANSLATE_QUERIES:
            raise Unavailable(
                f"{embedding.MODEL_NAME} is English-only and query translation is "
                "off — refusing to embed Bangla rather than retrieve arbitrary "
                "passages. Set BHAROSHA_TRANSLATE_QUERIES=on."
            )
        key = to_english(query)
    elif TRANSLATE_QUERIES and language != "en":
        key = to_english(query)
    found = search(key, n_results)
    return Retrieval(
        passages=[p for p in found if p.distance <= RELEVANCE_FLOOR],
        candidates=found,
        nearest=min((p.distance for p in found), default=None),
    )


# --- generation ------------------------------------------------------------


def answer(
    question: str,
    passages: list[Passage],
    history: list[tuple[str, str]] | None = None,
    language: str = "en",
    grounded: bool = True,
    category: str | None = None,
    block_mode: str | None = None,
    retry_note: str = "",
) -> str:
    """One reply. The only generation path there is.

    `question` is the RAW message — not normalised, not translated. The
    translation in this module produces a RETRIEVAL KEY and nothing else. A
    model shown "kemon acho" answers in Bangla on its own; a model shown "how
    are you" has already lost that, and nobody would ever know why.

    `passages` go in whether or not they cleared the floor. `grounded` says
    which they are: True licenses the model to answer from them, False tells it
    they are probably irrelevant and that it may converse but may not assert.
    That is the whole of what the gate now controls.

    Raises Unavailable on any failure, and the caller then sends the hardcoded
    text for the category — so a model outage becomes a complete referral with
    real phone numbers rather than an error the app has to interpret.
    """
    from langchain_core.prompts import PromptTemplate
    from langchain_groq import ChatGroq

    if not os.getenv("GROQ_API_KEY"):
        raise Unavailable("GROQ_API_KEY is not set")

    # Generation reads the language-appropriate side of each pair. Retrieval
    # matched on English; what the model quotes from is WaterAid's Bangla where
    # it exists, so a Bangla answer is not a machine translation of English.
    context = "\n\n".join(
        f"[Passage {i}] (source: {p.source})\n{p.for_language(language)}"
        for i, p in enumerate(passages, start=1)
    )
    # A turn with an empty answer is a note the app left behind (see
    # sessions.note): rendered as a single line so the model reads it as an
    # event in the conversation, not as something it once said.
    history_text = (
        "\n".join(
            f"user: {q}\nbharosha: {a}" if a else q for q, a in (history or [])
        )
        or "none"
    )

    # Bangla script and romanised Bangla both get a reply in Bangla script —
    # the prompt says so in words, and this names the language for the caps
    # line. Named, not inferred: the safety layer decided it deterministically,
    # and leaving the model to work it out once produced a Bangla answer to an
    # English question.
    named = "English" if language == "en" else "Bangla"
    chain = PromptTemplate.from_template(PROMPT) | ChatGroq(
        # Warm when it may assert, cold when it may not.
        #
        # 0.3 keeps greetings from becoming a saved message by another name —
        # "hi" should not return the identical sentence every time. But below
        # the floor the model is under a PROHIBITION, and measured across runs
        # it obeyed it inconsistently: "ki korbo?" came back as a clarifying
        # question on one run and as a numbered list of procedural steps on the
        # next. A rule that holds four times in five is not a rule, so the path
        # where the rule matters is deterministic and therefore testable.
        temperature=0.3 if grounded else 0.0,
        model=MODEL,
        api_key=os.environ["GROQ_API_KEY"],
        max_tokens=ANSWER_MAX_TOKENS,
        reasoning_effort=REASONING_EFFORT,
    )
    try:
        response = chain.invoke(
            {
                "grounding_line": GROUNDED_LINE if grounded else UNGROUNDED_LINE,
                "app_note": app_note(category, block_mode),
                "examples": EXAMPLES,
                "retry_note": retry_note,
                "context": context or "none",
                "history": history_text,
                "question": question,
                "language": named,
                "language_caps": named.upper(),
            }
        )
    except Exception as exc:  # noqa: BLE001 - auth, network, rate limit, anything
        raise Unavailable(str(exc)) from exc

    return reject_if_unusable(
        response.content,
        (response.response_metadata or {}).get("finish_reason"),
        "answer",
    )
