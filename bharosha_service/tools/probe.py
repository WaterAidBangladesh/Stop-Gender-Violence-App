"""Fires a list of messages at a running service and prints the path each took.

    python tools/probe.py                    # the conversational spec's cases
    python tools/probe.py --thread           # one session, so history is live

Needs the service up with BHAROSHA_DEV_CONSOLE=on (`.\\dev.ps1`), because it
reads the trace that /console/ask returns — which category fired, whether the
device or the model answered, and how far the nearest chunk was.

Writes UTF-8 to a file rather than to the terminal by default: a Windows console
renders Bangla as boxes, and a run whose output cannot be read proves nothing.
"""

from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import os

BASE = os.getenv("BHAROSHA_BASE", "http://127.0.0.1:8000")
OUT = Path(__file__).resolve().parents[1] / "probe_results.md"

# The cases from the conversational spec, in both languages, plus the boundaries
# either side of each one.
CASES: list[tuple[str, list[str]]] = [
    ("The spec's own list", [
        "ekta proshno kori tomake?",
        "তোমাকে একটা প্রশ্ন করি?",
        "achha bujhlam",
        "আচ্ছা বুঝলাম",
        "hmm",
        "হুম",
        "tumi ki help korte parbe?",
        "তুমি কি সাহায্য করতে পারবে?",
        "ki korbo?",
        "আমি কি করবো?",
        "how do I cook rice",
        "what is gender based violence",
        "জেন্ডারভিত্তিক সহিংসতা কী",
        "my husband hits me",
        "he is going to kill me",
    ]),
    ("Other social turns, now model-written", [
        "hi",
        "নমস্কার",
        "thank you",
        "ধন্যবাদ",
        "you are useless",
        "who are you?",
        "will my husband see this",
    ]),
    ("A friend, and the tail that used to get a wall", [
        "my friend is being abused by her husband",
        "আমার বান্ধবী নির্যাতনের শিকার",
        "I want to talk to someone",
        "what is the capital of France",
        "asdfgh",
        "tell me more",
    ]),
    ("Must stay on the device, in milliseconds", [
        "he is beating me right now",
        "আমাকে মারছে, বাঁচান",
        "I want to die",
        "they want to marry off my daughter",
        "should I leave my husband?",
        "will I win the case?",
        "my boss touches me at work",
        "I feel so alone",
    ]),
]

# A clarifying question is worthless if the next turn has forgotten what was
# being clarified. This runs in ONE session, in order.
THREAD = [
    "ekta proshno kori?",
    "amar office e ekjon achen",
    "ki korbo?",
    "hmm",
    "tomake dhonnobad",
]

# The same "ki korbo?" as the FIRST thing anyone types. It must get the bundled
# clarifier, because there is nothing to be contextual about and because the
# first message has to work with the radio off.
COLD = "ki korbo?"


def ask(session: str, query: str) -> dict:
    request = urllib.request.Request(
        f"{BASE}/console/ask",
        data=json.dumps({"session_id": session, "query": query}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())


def ask_safely(session: str, query: str) -> dict:
    """One slow Groq call must not end a fifty-message run."""
    try:
        return ask(session, query)
    except Exception as failure:  # noqa: BLE001 - this is a probe, report and go on
        return {"kind": "PROBE ERROR", "response": str(failure), "trace": {}}


def path_of(trace: dict) -> str:
    """The one-line answer to "which path did this take, and with what licence?"."""
    if trace.get("answered_by") == "device" and not trace.get("fell_back"):
        return f"DEVICE (bundled) / {trace.get('category')}"
    if trace.get("fell_back"):
        return f"bundled fallback / {trace.get('category')} — {trace['fell_back']}"
    if trace.get("kind") == "starting":
        return "bundled / still embedding the corpus"
    if "grounded" in trace:
        licence = "may assert" if trace["grounded"] else "MAY NOT ASSERT"
        return f"MODEL ({licence})"
    return f"bundled / {trace.get('kind')}"


def wait_for_corpus(attempts: int = 60) -> bool:
    """Block until a known-good question is actually answered.

    /health returns ok the moment the port is bound, by design — the corpus is
    still embedding for the next half-minute. A run started in that window
    measures the startup message instead of the behaviour, which has now
    happened twice.
    """
    import time

    for _ in range(attempts):
        try:
            if ask("probe-readiness", "what is safeguarding")["kind"] == "answer":
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(2)
    return False


def run(out: io.TextIOBase) -> None:
    for heading, messages in CASES:
        out.write(f"\n## {heading}\n\n")
        for message in messages:
            # A fresh session per message here, so each case is measured on its
            # own rather than on whatever the previous one left behind.
            result = ask_safely(f"probe-{uuid.uuid4().hex[:12]}", message)
            trace = result.get("trace", {})
            out.write(f"### `{message}`\n\n")
            out.write(f"- **path**: {path_of(trace)}\n")
            out.write(f"- kind `{result['kind']}` · {trace.get('language')} · "
                      f"{trace.get('ms')} ms")
            if trace.get("nearest") is not None:
                out.write(f" · nearest {trace['nearest']:.3f}")
            out.write("\n\n")
            out.write("> " + result["response"].replace("\n", "\n> ") + "\n")

    out.write("\n## The same message, cold\n\n")
    cold = ask(f"probe-cold-{uuid.uuid4().hex[:8]}", COLD)
    out.write(f"### `{COLD}` as the first message\n\n")
    out.write(f"- **path**: {path_of(cold.get('trace', {}))}\n\n")
    out.write("> " + cold["response"].replace("\n", "\n> ") + "\n")

    out.write("\n## One conversation, in order — does it remember?\n\n")
    session = f"probe-thread-{uuid.uuid4().hex[:8]}"
    for message in THREAD:
        result = ask_safely(session, message)
        trace = result.get("trace", {})
        out.write(f"### `{message}`\n\n- **path**: {path_of(trace)}\n\n")
        out.write("> " + result["response"].replace("\n", "\n> ") + "\n")


def main() -> int:
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=5):
            pass
    except (urllib.error.URLError, OSError) as failure:
        print(f"service not reachable at {BASE} — start it with .\\dev.ps1 ({failure})")
        return 1

    print("waiting for the corpus to finish embedding...")
    if not wait_for_corpus():
        print("the corpus never became ready — check the service log")
        return 1

    with OUT.open("w", encoding="utf-8") as out:
        out.write("# Probe results\n")
        out.write("\nGenerated by tools/probe.py against a running service.\n")
        run(out)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
