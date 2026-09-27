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
        ("Should I leave my husband?", "refusal"),
        ("Will I win the case?", "refusal"),
    ],
)
def test_emergency_and_refusal_served_with_no_models_loaded(
    message: str, expected_kind: str
) -> None:
    """No index, no embedder, no reranker, no Groq key — still answered."""
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
    without opening the index or loading the embedder."""
    result = api.health()
    assert result["status"] == "ok"
    assert "chain" not in sys.modules, "/health pulled the retrieval chain in"


def test_nothing_is_logged_or_counted() -> None:
    """There is no telemetry at all — not even counters.

    The earlier design kept aggregate counters; that was dropped in favour of
    recording nothing, which is strictly more private and removes the question of
    where counts would persist on an ephemeral filesystem. This test fails if a
    metrics module reappears and api.py starts using it.
    """
    assert not hasattr(api, "metrics")
    assert not (ROOT / "app" / "metrics.py").exists()
