"""Bharosha's HTTP surface.

    POST /chat       {session_id, query, category?} -> {response, kind}
    POST /chat/note  {session_id, category}         -> records an emergency the
                                                       phone answered itself
    POST /forget     {session_id}                   -> drops that conversation
    GET  /health                      -> cheap, does not touch the model

THE ORDER OF THIS FILE IS THE SAFETY DESIGN. Module-level imports are limited to
safety, referrals, sessions and ratelimit — none of which import chromadb,
fastembed or langchain. So from the moment uvicorn binds the port:

    1. safety.classify() runs first on every message. An emergency or a refusal
       returns hardcoded referral text immediately: no retrieval, no Groq call,
       no rate limiting, nothing to load first.
    2. Only messages that clear the safety layer are rate limited.
    3. Only then is the index opened (lazily, on first use) and queried.
    4. Retrieval must clear the distance gate, or a hardcoded referral is
       returned and the model is never called. Which referral depends on how
       far the nearest chunk was: a question that belongs here and missed gets
       the full no-context reply, a question about something else gets one
       line. The gate itself is untouched by that choice.
    5. Any failure — missing index, missing key, Groq outage — falls back to
       that same referral text.

Every path therefore ends with real phone numbers. The same detection now also
runs on the device in Dart, so referrals appear instantly and offline; this copy
is defence in depth for older app versions that still post raw questions here.

NOTHING IS LOGGED. No question text, no answer text, no session id, no address,
no counters. The service keeps ephemeral conversation state in memory and
forgets it on restart.
"""

from __future__ import annotations

import contextlib
import os
import threading
import time
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

import assertions
import ratelimit
import referrals
import safety
import sessions


def _background_load() -> None:
    """Embed the corpus on a thread. The import happens HERE, not at module
    level and not in the lifespan body, so binding the port waits for neither
    fastembed's import nor the embedding of 37 chunks."""
    import chain

    chain.load()


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    threading.Thread(target=_background_load, name="bharosha-corpus", daemon=True).start()
    yield


app = FastAPI(title="Bharosha", lifespan=lifespan, docs_url=None, redoc_url=None)


class ChatRequest(BaseModel):
    """What the app sends.

    session_id is a random UUID the device generates per conversation — never the
    Firebase uid, never anything derived from the user's identity. The server
    treats it as an opaque key for ephemeral history and nothing else.
    """

    session_id: Annotated[str, Field(min_length=8, max_length=64)]
    query: Annotated[str, Field(min_length=1, max_length=2000)]
    # What the phone's safety layer decided. ADVISORY ONLY: the server runs the
    # same classifier and trusts its own result, so a tampered or stale client
    # cannot route a disclosure as small talk. It is carried so that a mismatch
    # between the two shows up in the dev console instead of going unnoticed.
    category: Annotated[str | None, Field(max_length=40)] = None


class ForgetRequest(BaseModel):
    session_id: Annotated[str, Field(min_length=8, max_length=64)]


class NoteRequest(BaseModel):
    """The phone answered an emergency itself and is telling the server so.

    A category name only. Validated against the emergency list below, so this
    endpoint cannot be used to put free text into anyone's history.
    """

    session_id: Annotated[str, Field(min_length=8, max_length=64)]
    category: Annotated[str, Field(min_length=1, max_length=40)]


def _reply(category: str, language: str, kind: str) -> dict[str, str]:
    return {"response": referrals.response_for(category, language), "kind": kind}


def _answer(
    query: str,
    session_id: str,
    caller: str | None,
    trace: dict | None = None,
    client_category: str | None = None,
) -> dict[str, str]:
    """The whole pipeline. One copy, called by /chat and by the dev console.

    `trace` is filled in as it goes when a dict is passed. It is a WRITE-ONLY
    output: nothing in here ever reads it or behaves differently because it is
    present, so the console sees exactly the pipeline the app sees. /chat passes
    None and its response shape is unchanged.
    """

    def note(**fields: object) -> None:
        if trace is not None:
            trace.update(fields)

    # ---- 1. Safety first, always, before anything is loaded or called ------
    decision = safety.classify(query)
    note(
        kind=decision.kind,
        category=decision.category,
        language=decision.language,
        matched=list(decision.matched),
        answered_by="device" if decision.stops_turn else "server",
    )
    if client_category is not None and client_category != decision.category:
        # Never acted on — the server's own classification is the one that
        # counts. Surfaced so a phone build whose bundled rules have fallen
        # behind is visible in the console rather than silently disagreeing.
        note(client_category=client_category, client_disagrees=True)

    # ANSWERED HERE, FROM FIXED TEXT, IN MICROSECONDS. The list is
    # safety.DEVICE_CATEGORIES — the five emergencies and nothing else. Nothing
    # is loaded, nothing is called, and none of it depends on a network the
    # phone may not have. Every other category is classified here too, but the
    # model writes the reply and code appends the referral block.
    if decision.stops_turn:
        return _reply(decision.category, decision.language, decision.kind)

    # ---- 2. Everything else goes to the model. One path. -------------------
    #
    # A greeting, a thank you, "hmm", a friend in trouble, a question about
    # economic violence, a question about cooking — all of them from here on
    # take the same code path and all of them reach the model. There is no
    # longer a "cleared the gate" branch and a "fell through to a fixed wall"
    # branch; that second branch is what made the app feel like a set of saved
    # replies.
    #
    # Rate limited, because this is the part that costs money and there is no
    # login in front of it. Nothing urgent reaches here — it was all answered
    # above.
    if caller is not None and not ratelimit.allow(caller):
        # A category with its own text gets its own text, not "try again
        # shortly". Someone asking how to help an abused friend should not be
        # turned away with a thin apology because the last person asked twice —
        # and returning it costs nothing, which is why it was never the thing
        # the limiter was protecting.
        if decision.category and decision.category in referrals.RESPONSES:
            return _reply(decision.category, decision.language, decision.kind)
        return _reply("rate_limited", decision.language, "rate_limited")

    import chain  # noqa: PLC0415 - kept off the import path; see module docstring

    def fallback(reason: str, nearest: float | None = None) -> dict[str, str]:
        """What she gets when the model cannot be reached.

        The category's own hardcoded text if it has one — a greeting still gets
        the greeting, a vague message still gets the clarifier, a third-party
        concern still gets the full support script. Only an ordinary question
        has no text of its own, and that is the one case that falls to the
        tiered no-context / off-topic pair. Nothing that used to work offline
        has stopped working offline.
        """
        note(fell_back=reason)
        if decision.category and decision.category in referrals.RESPONSES:
            return _reply(decision.category, decision.language, decision.kind)
        far = nearest is not None and nearest > chain.OFF_TOPIC_DISTANCE
        category = "off_topic" if far else "no_context"
        note(kind=category, category=category)
        return _reply(category, decision.language, category)

    try:
        found = chain.retrieve_scored(query, decision.language)
    except chain.NotReady as failure:
        # A category with its own text gets its own text: a disclosure typed
        # in the half-minute after a restart must not be answered with "I am
        # still starting up". Only an uncategorised question waits — and it
        # is told so honestly, because "I don't have reliable information
        # about that" would be a claim about her question when the truth is
        # that it was never looked up.
        note(retrieval_error=str(failure))
        if decision.category and decision.category in referrals.RESPONSES:
            note(fell_back="corpus not ready")
            return _reply(decision.category, decision.language, decision.kind)
        note(kind="starting", category="starting")
        return _reply("starting", decision.language, "starting")
    except chain.Unavailable as failure:
        return fallback(str(failure))

    # THE GATE, REFRAMED. It no longer decides whether she gets a reply. It
    # decides what the model may ASSERT: above the floor, answer from these
    # passages; below it, they are probably irrelevant, so converse, ask one
    # question, point to a person — and state no safeguarding, health, legal or
    # procedural fact. The floor and its measurement are unchanged.
    grounded = bool(found.passages)
    note(
        grounded=grounded,
        nearest=found.nearest,
        gate=chain.RELEVANCE_FLOOR,
        passages=[
            {"distance": round(p.distance, 3), "source": p.source}
            for p in found.candidates
        ],
    )

    # ---- 3b. Decide what code will append, BEFORE the model writes --------
    #
    # SAFETY DECIDES, THE AI SPEAKS. For a recognised category the model
    # writes the words and code appends the referral block from referrals.py
    # — the contacts and the one sentence of limit — so the numbers never
    # come from the model and the limit is never softened by it. The block is
    # full the first time this category's contacts appear in the conversation
    # and one line after that. Decided here rather than after, because the
    # model is told which size will follow its reply.
    block_mode = (
        sessions.store.block_mode(session_id, decision.category)
        if referrals.has_block(decision.category)
        else None
    )
    note(block=block_mode)

    try:
        text = chain.answer(
            query,
            found.passages if grounded else found.candidates,
            sessions.store.history(session_id),
            language=decision.language,
            grounded=grounded,
            category=decision.category,
            block_mode=block_mode,
        )
    except chain.Unavailable as failure:
        return fallback(str(failure), found.nearest)

    # ---- 4. Check the output, do not trust the prohibition -----------------
    #
    # Below the floor the model was told it may converse but may not state a
    # safeguarding, health, legal or procedural fact. Measured, it obeys that
    # most of the time and not all of the time — so compliance is verified, not
    # assumed, in exactly the way emergency detection is. On a match the reply
    # is DISCARDED and she gets the hardcoded text, which is the same thing a
    # model outage produces. A reply that broke the rule is not evidence about
    # what the right reply was.
    if not grounded:
        marker = assertions.asserts_anyway(text)
        assertions.counter.record(discarded=marker is not None)
        if marker:
            return fallback(f"asserted anyway: {marker!r}", found.nearest)

    # ---- 5. Append what code owns ------------------------------------------
    #
    # Only when a safety category matched. An ordinary grounded question gets
    # the model's words and nothing else: the automatic footer that used to
    # follow every answer is gone, because the call buttons are on screen for
    # the whole conversation and a helpline paragraph under "what is economic
    # violence?" was the leaflet-rack feel in miniature.
    if block_mode is not None:
        text = text + "\n\n" + referrals.referral_block(
            decision.category, decision.language, block_mode
        )

    # The whole reply — model text and block — goes into history, so on the
    # next turn the model knows what she has already been shown.
    sessions.store.record(session_id, query, text)
    note(kind="answer", model=chain.MODEL)
    return {"response": text, "kind": decision.kind if decision.category else "answer"}


@app.post("/chat")
def chat(request: ChatRequest, http: Request) -> dict[str, str]:
    return _answer(
        request.query,
        request.session_id,
        ratelimit.client_key(
            http.headers.get("x-forwarded-for"),
            http.client.host if http.client else None,
        ),
        client_category=request.category,
    )


@app.post("/chat/note")
def chat_note(request: NoteRequest) -> dict[str, bool]:
    """Fire-and-forget from the phone after it showed an emergency reply.

    Fills the hole in the model's memory where the worst moment was — with a
    category label, never her words. Anything other than a known emergency
    category is refused, so no client can write text into a history through
    this door.
    """
    if request.category not in safety.EMERGENCY_CATEGORIES:
        return {"noted": False}
    sessions.store.note(request.session_id, request.category)
    return {"noted": True}


@app.post("/forget")
def forget(request: ForgetRequest) -> dict[str, bool]:
    """Drop a conversation. The app calls this when the chat is closed."""
    sessions.store.forget(request.session_id)
    return {"forgotten": True}


# --- the development console ------------------------------------------------
#
# OFF UNLESS ASKED FOR. Two routes exist only when BHAROSHA_DEV_CONSOLE=on, so a
# deployed instance does not serve them at all — not hidden, not authenticated,
# absent. They are registered inside an `if`, which is the only form of that
# guarantee that cannot be defeated by a config mistake.
#
# WHY IT EXISTS. Checking a change meant launching the Flutter app, which takes
# minutes, and reading the reply in a Windows terminal, which renders Bangla as
# boxes. The console is a browser page, so Bangla is Bangla, and it shows the
# things the app deliberately hides: which category fired, whether the answer
# came from the device or the model, the nearest distance and where it fell
# relative to the gate.
#
# It calls the SAME _answer() the app calls. It does not re-implement the
# pipeline, and the trace it prints is written as that pipeline runs, so the
# console cannot show you something different from what the phone would get.
DEV_CONSOLE = os.getenv("BHAROSHA_DEV_CONSOLE", "off").lower() in ("on", "1", "true")

if DEV_CONSOLE:
    CONSOLE_HTML = Path(__file__).resolve().parents[1] / "tools" / "console.html"

    class ConsoleRequest(BaseModel):
        session_id: Annotated[str, Field(min_length=8, max_length=64)]
        query: Annotated[str, Field(min_length=1, max_length=2000)]
        category: Annotated[str | None, Field(max_length=40)] = None

    @app.get("/console", response_class=HTMLResponse)
    def console() -> str:
        return CONSOLE_HTML.read_text(encoding="utf-8")

    @app.post("/console/ask")
    def console_ask(request: ConsoleRequest) -> dict:
        trace: dict = {}
        started = time.perf_counter()
        # No rate-limit key: the whole point of this page is to fire forty
        # messages at it in a row. See the guard in _answer.
        reply = _answer(
            request.query, request.session_id, None, trace,
            client_category=request.category,
        )
        trace["ms"] = round((time.perf_counter() - started) * 1000)
        return {**reply, "trace": trace}


@app.get("/health")
def health() -> dict[str, object]:
    """Cheap on purpose, so the platform's health check does not load the model
    or wake the embedder — and so a slow first load never looks like a crash."""
    return {
        "status": "ok",
        "sessions": sessions.store.count(),
        # Counters only — no text, no ids, nothing timestamped. How often the
        # model broke the below-floor prohibition and had its reply discarded.
        **assertions.counter.snapshot(),
    }
