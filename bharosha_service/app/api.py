"""Bharosha's HTTP surface.

    POST /chat    {session_id, query} -> {response, kind}
    POST /forget  {session_id}        -> drops that conversation
    GET  /health                      -> cheap, does not touch the model

THE ORDER OF THIS FILE IS THE SAFETY DESIGN. Module-level imports are limited to
safety, referrals, sessions and ratelimit — none of which import chromadb,
fastembed or langchain. So from the moment uvicorn binds the port:

    1. safety.classify() runs first on every message. An emergency or a refusal
       returns hardcoded referral text immediately: no retrieval, no Groq call,
       no rate limiting, nothing to load first.
    2. Only messages that clear the safety layer are rate limited.
    3. Only then is the index opened (lazily, on first use) and queried.
    4. Retrieval must clear the distance gate, or the hardcoded no-context
       referral is returned and the model is never called.
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
import threading
from typing import Annotated

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

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


class ForgetRequest(BaseModel):
    session_id: Annotated[str, Field(min_length=8, max_length=64)]


def _reply(category: str, language: str, kind: str) -> dict[str, str]:
    return {"response": referrals.response_for(category, language), "kind": kind}


@app.post("/chat")
def chat(request: ChatRequest, http: Request) -> dict[str, str]:
    # ---- 1. Safety first, always, before anything is loaded or called ------
    decision = safety.classify(request.query)

    if decision.kind == "emergency":
        return _reply(decision.category, decision.language, "emergency")

    if decision.kind == "refuse":
        return _reply(decision.category, decision.language, "refusal")

    # A greeting costs nothing to answer and needs no corpus. Before the rate
    # limiter for the same reason emergencies are: it never reaches the model.
    if decision.kind == "greeting":
        return _reply(decision.category, decision.language, "greeting")

    # ---- 2. Rate limiting, only for messages that may reach the model ------
    # Emergencies and refusals never reach here: they cost nothing to serve, and
    # nobody in danger is turned away for asking twice.
    caller = ratelimit.client_key(
        http.headers.get("x-forwarded-for"),
        http.client.host if http.client else None,
    )
    if not ratelimit.allow(caller):
        return _reply("rate_limited", decision.language, "rate_limited")

    # ---- 3. Retrieval, behind the distance gate ---------------------------
    import chain  # noqa: PLC0415 - kept off the import path; see module docstring

    try:
        # Any failure here — corpus still embedding, corpus missing, a failed
        # query translation — falls through to the referral, never to an
        # ungated retrieval and never to a model call without context.
        passages = chain.retrieve(request.query, decision.language)
    except chain.Unavailable:
        return _reply("no_context", decision.language, "no_context")

    if not passages:
        return _reply("no_context", decision.language, "no_context")

    # ---- 4. The model, with the referral footer added afterwards -----------
    try:
        text = chain.answer(
            request.query,
            passages,
            sessions.store.history(request.session_id),
            language=decision.language,
        )
    except chain.Unavailable:
        return _reply("no_context", decision.language, "no_context")

    sessions.store.record(request.session_id, request.query, text)
    return {
        "response": text + referrals.answer_footer(decision.language),
        "kind": "answer",
    }


@app.post("/forget")
def forget(request: ForgetRequest) -> dict[str, bool]:
    """Drop a conversation. The app calls this when the chat is closed."""
    sessions.store.forget(request.session_id)
    return {"forgotten": True}


@app.get("/health")
def health() -> dict[str, object]:
    """Cheap on purpose, so the platform's health check does not load the model
    or wake the embedder — and so a slow first load never looks like a crash."""
    return {"status": "ok", "sessions": sessions.store.count()}
