"""The emergency path must work before, and without, any model.

This is the service's single most important runtime property: a cold or
still-starting container must return correct referrals instantly. It is
structural, not a matter of care — so it is tested rather than asserted in a
comment.

Run from bharosha_service/:  python -m pytest -q
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import api  # noqa: E402
import ratelimit  # noqa: E402
import referrals  # noqa: E402


def _http(forwarded_for: str | None = None, host: str = "203.0.113.5"):
    """A stand-in for Starlette's Request, carrying only what /chat reads."""
    headers = {"x-forwarded-for": forwarded_for} if forwarded_for else {}
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=host))


def test_importing_api_does_not_load_any_model() -> None:
    """chromadb, fastembed and langchain must not be imported by api.py.

    If they are, the port does not open until they finish importing, and the
    emergency path — which needs none of them — is delayed behind them.
    Subprocess, so the check is not polluted by other tests' imports.
    """
    code = (
        "import sys; sys.path.insert(0, 'app'); import api; "
        "print(','.join(m for m in "
        "('torch','chromadb','fastembed','onnxruntime','sentence_transformers',"
        "'langchain_groq','langchain_core') "
        "if m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    leaked = result.stdout.strip()
    assert leaked == "", f"api.py pulled heavy modules at import time: {leaked}"


@pytest.mark.parametrize(
    "message, expected_kind",
    [
        ("He is beating me right now", "emergency"),
        ("আমাকে মারছে, বাঁচান", "emergency"),
        ("I want to die", "emergency"),
        ("my daughter was touched by her teacher", "emergency"),
        ("Should I leave my husband?", "refuse"),
        ("Will I win the case?", "refuse"),
    ],
)
def test_emergency_and_refusal_served_with_no_models_loaded(
    message: str, expected_kind: str
) -> None:
    """No index, no embedder, no reranker, no Groq key — still answered.

    An emergency never gets as far as the corpus. A refusal now does, and with
    the corpus not yet embedded it must come back as its own fixed text — not
    as "I am still starting up", which is the reply for a question that has
    no text of its own.
    """
    result = api.chat(
        api.ChatRequest(session_id="test-session-1234", query=message),
        _http(),
    )
    assert result["kind"] == expected_kind
    assert result["response"].strip()
    # Every such reply must carry a real number from the app's own list.
    assert any(line.number in result["response"] for line in referrals.NATIONAL_HELPLINES)


def test_emergency_is_not_rate_limited() -> None:
    """A person in danger is never turned away for asking twice.

    Exhausts the limiter for one caller, then checks an emergency still gets
    its referral — it costs nothing to serve, so the limiter is not consulted.
    """
    caller = "198.51.100.77"
    for _ in range(ratelimit.BURST + 5):
        ratelimit.allow(caller)
    assert ratelimit.allow(caller) is False, "limiter should be exhausted"

    result = api.chat(
        api.ChatRequest(session_id="test-session-5678", query="he will kill me"),
        _http(forwarded_for=caller),
    )
    assert result["kind"] == "emergency"
    assert "999" in result["response"]


def test_forwarded_for_parsing() -> None:
    """The caller's address, taken from the right, not the spoofable left."""
    # client, then Render's proxy: one trusted hop means take "70.41.3.18".
    assert ratelimit.client_key("203.0.113.9, 70.41.3.18", "10.0.0.1") == "70.41.3.18"
    # A single entry is the client as seen by our proxy.
    assert ratelimit.client_key("203.0.113.9", "10.0.0.1") == "203.0.113.9"
    # No header: fall back to the socket.
    assert ratelimit.client_key(None, "10.0.0.1") == "10.0.0.1"
    assert ratelimit.client_key("", None) == "unknown"


def test_health_does_not_touch_the_model() -> None:
    """Render restarts a service whose health check fails, so it must answer
    without opening the index or loading the embedder.

    Checked in a subprocess: asserting on sys.modules in-process only proves
    that no OTHER test imported chain first, which is a property of the test
    suite rather than of /health.
    """
    code = (
        "import sys; sys.path.insert(0, 'app'); import api; "
        "r = api.health(); assert r['status'] == 'ok'; "
        "print('chain' in sys.modules or 'fastembed' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False", "/health pulled the retrieval chain in"


def test_nothing_is_logged_or_counted() -> None:
    """There is no telemetry at all — not even counters.

    The earlier design kept aggregate counters; that was dropped in favour of
    recording nothing, which is strictly more private and removes the question of
    where counts would persist on an ephemeral filesystem. This test fails if a
    metrics module reappears and api.py starts using it.
    """
    assert not hasattr(api, "metrics")
    assert not (ROOT / "app" / "metrics.py").exists()


# --- the development console ------------------------------------------------


def test_console_is_absent_unless_asked_for() -> None:
    """Not hidden, not authenticated — ABSENT.

    The routes are registered inside `if DEV_CONSOLE:`, so a deployed instance
    does not have them at all. This is the test that keeps that true: a console
    that 404s because of a config value can be turned on by a config mistake.
    """
    import api
    from fastapi.testclient import TestClient

    assert api.DEV_CONSOLE is False, "BHAROSHA_DEV_CONSOLE must default to off"
    client = TestClient(api.app)
    assert client.get("/console").status_code == 404
    assert client.post(
        "/console/ask", json={"session_id": "x" * 10, "query": "hi"}
    ).status_code == 404


def test_chat_response_shape_is_unchanged_by_the_console() -> None:
    """The app's endpoint must return exactly what it always returned.

    The console gets its diagnostics from a trace dict that _answer() writes
    into; /chat passes None, so nothing extra can leak into the response the
    phone parses.
    """
    import api
    from fastapi.testclient import TestClient

    body = TestClient(api.app).post(
        "/chat", json={"session_id": "x" * 10, "query": "hi"}
    ).json()
    assert set(body) == {"response", "kind"}


def test_a_question_asked_before_the_corpus_loads_says_so() -> None:
    """"I don't have reliable information about that" is a claim about her
    question. While the corpus is still embedding it is false — the question was
    never looked up. That text existed and was tested from the first version,
    and nothing returned it until the dev console made the difference visible.
    """
    import api
    import chain
    import referrals
    from fastapi.testclient import TestClient

    def not_loaded(*_args, **_kwargs):
        raise chain.NotReady("corpus not loaded yet")

    original = chain.retrieve_scored
    chain.retrieve_scored = not_loaded
    try:
        body = TestClient(api.app).post(
            "/chat", json={"session_id": "x" * 10, "query": "what is safeguarding?"}
        ).json()
    finally:
        chain.retrieve_scored = original

    assert body["kind"] == "starting"
    assert body["response"] == referrals.response_for("starting", "en")


def test_an_emergency_never_touches_the_model(monkeypatch) -> None:
    """The one rule the whole design rests on.

    Everything except the five emergencies now reaches the model, so this
    test matters more than it did, not less: it pins the line between what was
    opened up and what was not. Every retrieval and generation entry point is
    made to explode; an emergency must still return its script, untouched.
    """
    import api
    import chain
    import referrals
    from fastapi.testclient import TestClient

    def explode(*_args, **_kwargs):
        raise AssertionError("an emergency reached the model")

    for name in ("retrieve_scored", "search", "answer", "to_english"):
        monkeypatch.setattr(chain, name, explode)

    client = TestClient(api.app)
    for message, category in [
        ("he is beating me right now", "active_violence"),
        ("I want to die", "suicide_risk"),
        ("he said he will kill me", "threat_to_life"),
        ("they want to marry off my daughter", "child_disclosure"),
        ("আমাকে মারছে, বাঁচান", "immediate_danger"),
    ]:
        body = client.post(
            "/chat", json={"session_id": "x" * 10, "query": message}
        ).json()
        language = "bn" if category == "immediate_danger" else "en"
        assert body["response"] == referrals.response_for(category, language), message


def test_a_stale_client_category_is_not_trusted() -> None:
    """The phone sends what it decided. The server decides again.

    A tampered or out-of-date app that labels "he is going to kill me" as a
    greeting must still get the emergency script, and one that labels "hi" as
    an emergency must not get 999 for saying hello.
    """
    import api
    import referrals
    from fastapi.testclient import TestClient

    client = TestClient(api.app)
    body = client.post(
        "/chat",
        json={"session_id": "x" * 10, "query": "he is going to kill me",
              "category": "greeting"},
    ).json()
    assert body["response"] == referrals.response_for("threat_to_life", "en")

    body = client.post(
        "/chat",
        json={"session_id": "x" * 10, "query": "hi", "category": "active_violence"},
    ).json()
    assert body["kind"] != "emergency"
    assert "999" not in body["response"].split("\n")[0]


def test_every_model_path_falls_back_to_its_own_hardcoded_text(
    monkeypatch,
) -> None:
    """THE FLOOR DID NOT MOVE.

    Greetings, thanks, vague messages and third-party concerns now go to the
    model. When it cannot be reached they must still produce the text they
    produced when they were hardcoded — not a generic apology, and not the
    no-context wall. Only an ordinary question has no text of its own, and that
    is the single case that falls to the tiered pair.
    """
    import api
    import chain
    import referrals
    from fastapi.testclient import TestClient

    def unavailable(*_args, **_kwargs):
        raise chain.Unavailable("no key, no network, pick one")

    monkeypatch.setattr(chain, "retrieve_scored", unavailable)
    client = TestClient(api.app)

    # A distinct caller per message: this measures the fallback, not the rate
    # limiter, which would otherwise start answering halfway through.
    def post(message: str, n: int) -> dict:
        return client.post(
            "/chat",
            json={"session_id": "x" * 10, "query": message},
            headers={"x-forwarded-for": f"203.0.113.{n + 40}"},
        ).json()

    for n, (message, category) in enumerate([
        ("hello", "greeting"),
        ("thank you", "thanks"),
        ("hmm", "acknowledgement"),
        ("you are useless", "bot_abuse"),
        ("help", "vague"),
        ("my friend is being abused by her husband", "third_party_concern"),
    ]):
        body = post(message, n)
        assert body["response"] == referrals.response_for(category, "en"), message

    # The one with no text of its own.
    body = post("what is safeguarding?", 99)
    assert body["response"] == referrals.response_for("no_context", "en")
