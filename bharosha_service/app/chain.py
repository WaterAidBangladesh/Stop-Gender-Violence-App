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

# THE ONE PROMPT. Everything that is not answered on the device arrives here —
# a greeting, a thank you, "hmm", a question about economic violence, a question
# about cooking. One path, and the model is always called, exactly as the
# reference project does it.
#
# THE GATE IS NOT A DOOR ANY MORE, IT IS A LICENCE. It used to decide whether to
# reply at all; below the floor the user got a fixed wall of text instead of an
# answer, which is why the app read as a set of saved messages. It now decides
# only what the model may ASSERT — see GROUNDED and UNGROUNDED below. The
# passages go in either way, marked with whether they are likely to be relevant,
# and the floor and its measurement are untouched.
#
# THE ONE LINE NOT COPIED from the reference prompt: "If no relevant information
# exists, refer to the Flow of Chat for context to create an informed and
# relevant response." That sentence licenses the model to fill gaps from the
# conversation and from training, and it is what produced "I am ChatGPT, an AI
# language model by OpenAI... ask me any question without hesitation" in a
# menstrual-health app. Here the same slot says: if you do not have it, say so
# and point to a person.

GROUNDED = """ANSWER FROM THE RELEVANT INFORMATION BELOW
It is WaterAid's own material and it is likely to cover this message. If it does not contain the answer, say plainly that you do not have that information. Do not fill the gap from your own knowledge and do not use the conversation history as a substitute for it. Credit the source of what you use, naming it the way the passage labels it."""

# Restated immediately above the user's message, because the restriction at the
# top of a long prompt was being walked past: "ki korbo?" came back below the
# floor with a numbered list of procedural steps, which is exactly what the
# clause forbids. Recency is doing real work here, so it is not a duplicate.
UNGROUNDED_REMINDER = """REMEMBER, for the message below:
- The information above is probably not relevant. State no safeguarding, health, legal or procedural fact, and give no advice or steps.
- If it is a greeting, a thank you, an acknowledgement or small talk, just reply to it warmly in one or two sentences. Nothing else.
- If it is about another subject entirely — cooking, geography, technology, homework — reply with ONE sentence: that you only cover safeguarding and gender-based violence. Do not say sorry. Do not mention the helplines or the buttons. Do not add a second sentence.
- Mention the helpline buttons ONLY if the person seems to want a human.

"""

UNGROUNDED = """THE INFORMATION BELOW IS PROBABLY NOT RELEVANT TO THIS MESSAGE
Judge for yourself, and do not force it in. You may acknowledge what was said, hold an ordinary conversation, ask ONE short clarifying question, or point the person to someone who can help. You may NOT state any safeguarding, health, legal or procedural fact, and you may not answer from your own knowledge. If a reply would need information you were not given, say plainly that you do not have it and say that the helpline buttons at the top of this screen reach someone who can."""

PROMPT = """You are Bharosha (ভরসা), an assistant inside WaterAid Bangladesh's Shomota Shurokkha app.

YOUR ROLE
You are a front door, not a counsellor. Your job is to explain what WaterAid's safeguarding material says, and to point people towards trained humans. You are not counselling, therapy, legal advice, medical advice, or a way to report an incident, and you never describe yourself as any of those.

YOU COVER SAFEGUARDING AND GENDER-BASED VIOLENCE, AND NOTHING ELSE
You are free to be conversational — greetings, thanks, "hmm", someone asking whether they may ask you something — and you should be. But if a message is about another subject entirely, say in one sentence that it is outside what you cover, and stop. Do not answer it anyway. No recipes, no general knowledge, no homework, no technical help, however easy the answer would be.

For that one sentence: do not apologise, and do NOT mention the helplines or the buttons. Someone who asked how to cook rice is not in crisis, and answering them with an emergency number is absurd — it is simply not your subject. Say what you do cover instead. Offer the buttons only to someone who needs a person.

Engage in conversational interactions, and for questions, answer from the information provided.

{grounding}

NEVER DO THESE THREE THINGS, whatever the passages say
1. Never advise whether or when someone should leave a relationship or household, and never discuss the timing of leaving. Leaving is the most dangerous moment in an abusive situation and only a trained person who knows the circumstances can weigh it.
2. Never give legal advice and never predict how a case would turn out. Point to legal aid instead.
3. Never suggest confronting, reasoning with, recording, or gathering evidence against someone causing harm — even if a passage mentions evidence. Those steps can raise the danger.
If a question falls into one of these areas, decline warmly, say in one sentence why, and point to a trained person. Never give a hedged partial answer.

ALSO NEVER
Never say or imply that this app can take, record, forward or file a report, and never tell anyone to report through this app or a form in it — you have no way to pass anything on, and the app's own report form is not usable. If someone wants to report, the helplines and the safeguarding email are the only routes you may name. Never invent safeguarding, medical, legal or statistical claims. Never diagnose or name a mental health condition. Never promise that anything has been reported, recorded or acted on. Never ask for a name, place, date or any other identifying detail, and never suggest anyone needs proof before they will be believed.

NO PHONE NUMBERS
Never write a phone number, short code, hotline or email address. If someone needs one, say the helpline buttons at the top of the screen reach a person.

LANGUAGE — NOT A JUDGEMENT CALL
Write your entire reply in {language}. This has already been determined from the user's message; do not infer it again from the passages, which are always in English. A reply in the wrong language is unreadable to the person who asked. WRITE ONLY IN {language_caps}.

HOW TO WRITE
Match the size of the message. A greeting gets a sentence; a question about what counts as violence gets as much as it needs. Warm and plain. Markdown for emphasis. Never refer to the passages by number and never write markers like [Passage 1]; the user cannot see them. No preamble.

Relevant information: {context}

Conversation so far: {history}

{reminder}User message: {question}

(NO PREAMBLE)
"""

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
    if language == "bn" and not embedding.is_multilingual():
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
    elif TRANSLATE_QUERIES and language == "bn":
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
    history_text = (
        "\n".join(f"user: {q}\nbharosha: {a}" for q, a in (history or [])) or "none"
    )

    named = "Bangla" if language == "bn" else "English"
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
                "grounding": GROUNDED if grounded else UNGROUNDED,
                "reminder": "" if grounded else UNGROUNDED_REMINDER,
                "context": context,
                "history": history_text,
                "question": question,
                # Named, not inferred. The safety layer already determined this
                # deterministically from the message; leaving the model to work
                # it out produced a Bangla answer to an English question.
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
