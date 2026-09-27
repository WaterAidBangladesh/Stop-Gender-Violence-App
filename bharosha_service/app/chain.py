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

N_RESULTS = int(os.getenv("BHAROSHA_N_RESULTS", "4"))

MODEL = os.getenv("BHAROSHA_MODEL", "openai/gpt-oss-20b")

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

PROMPT = """You are Bharosha (ভরসা), an assistant inside WaterAid Bangladesh's Shomota Shurokkha app.

YOUR ROLE
You are a front door, not a counsellor. Your job is to explain what WaterAid's safeguarding material says, and to point people towards trained humans. You are not counselling, therapy, legal advice, medical advice, or a way to report an incident, and you never describe yourself as any of those.

ANSWER ONLY FROM THE RELEVANT INFORMATION BELOW
It is WaterAid's own material. If it does not contain the answer, say plainly that you do not have that information — do not fill the gap from your own knowledge, and do not use the conversation history as a substitute for it. Never invent safeguarding, medical, legal or statistical claims. Credit the source of what you use, naming it the way the passage labels it.

NEVER DO THESE THREE THINGS, whatever the passages say
1. Never advise whether or when someone should leave a relationship or household, and never discuss the timing of leaving. Leaving is the most dangerous moment in an abusive situation and only a trained person who knows the circumstances can weigh it.
2. Never give legal advice and never predict how a case would turn out. Point to legal aid instead.
3. Never suggest confronting, reasoning with, recording, or gathering evidence against someone causing harm — even if a passage mentions evidence. Those steps can raise the danger.
If a question falls into one of these areas, decline warmly, say in one sentence why, and point to a trained person. Never give a hedged partial answer.

NO PHONE NUMBERS
Never write a phone number, short code, hotline or email address. Referral numbers are added automatically after your answer. If someone needs one, say the numbers are shown below.

LANGUAGE — NOT A JUDGEMENT CALL
Write your entire reply in {language}. This has already been determined from the user's message; do not infer it again from the passages, which are always in English. A reply in the wrong language is unreadable to the person who asked.

HOW TO WRITE
Warm, plain and short: two or three short paragraphs at most. Markdown for emphasis and lists. Name the source of what you use, as the passage labels it — but never refer to the passages by number, and never write markers like [Passage 1]; the user cannot see them. Never judge, never ask for identifying details, never promise that anything has been reported. No preamble.

Relevant information: {context}

Conversation so far: {history}

User message: {question}

(NO PREAMBLE)
"""

TRANSLATE_PROMPT = (
    "Translate this question into English. It may be about safeguarding or "
    "gender-based violence; translate it faithfully and do not answer it, "
    "soften it, or add anything. Reply with the translation only.\n\n{question}"
)


class Unavailable(RuntimeError):
    """No answer could be produced. The caller falls back to referral text."""


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
            raise Unavailable(_error.splitlines()[-1] if _error else "corpus not loaded")
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
            temperature=0, model=MODEL, api_key=os.environ["GROQ_API_KEY"]
        )
        text = (chain.invoke({"question": question}).content or "").strip()
    except Exception as exc:  # noqa: BLE001
        raise Unavailable(f"translation failed: {exc}") from exc
    if not text:
        raise Unavailable("translation returned nothing")
    return text


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
    return [p for p in search(key, n_results) if p.distance <= RELEVANCE_FLOOR]


# --- generation ------------------------------------------------------------


def answer(
    question: str,
    passages: list[Passage],
    history: list[tuple[str, str]] | None = None,
    language: str = "en",
) -> str:
    """One answer, grounded in `passages`. Raises Unavailable on any failure.

    Raising rather than returning something degraded is the point: the caller
    answers with hardcoded referral text, so a model outage becomes a useful
    reply carrying real phone numbers instead of an error the app must interpret.
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

    chain = PromptTemplate.from_template(PROMPT) | ChatGroq(
        temperature=0, model=MODEL, api_key=os.environ["GROQ_API_KEY"]
    )
    try:
        response = chain.invoke(
            {
                "context": context,
                "history": history_text,
                "question": question,
                # Named, not inferred. The safety layer already determined this
                # deterministically from the message; leaving the model to work
                # it out produced a Bangla answer to an English question.
                "language": "Bangla" if language == "bn" else "English",
            }
        )
    except Exception as exc:  # noqa: BLE001 - auth, network, rate limit, anything
        raise Unavailable(str(exc)) from exc

    text = (response.content or "").strip()
    if not text:
        raise Unavailable("empty response")
    return text
