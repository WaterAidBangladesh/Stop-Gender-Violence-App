"""Ephemeral conversation memory, keyed by a random id from the device.

Probahini keys history by the app's Firebase user_id, which ties every question
a person asks to their identity for as long as the process lives. Here the
device generates a fresh UUID per conversation and sends that. The server never
learns who is asking, and two conversations from the same person are
unconnectable.

Properties that matter:

* Memory only. Never written to disk, a database, or a log. A restart forgets
  everything, which is the intended behaviour, not a limitation.
* Capped at MAX_TURNS, so a long conversation cannot grow the prompt without
  bound (and with it the cost and the chance of the model drifting off the
  retrieved passages).
* Expires after TTL_SECONDS of silence.
* Bounded in count, evicting the least recently used, so an attacker sending
  random session ids cannot exhaust memory.

Message text does live here while a conversation is active — that is what makes
it a conversation. It never reaches metrics, logs or storage.
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict, deque

MAX_TURNS = int(os.getenv("BHAROSHA_MAX_TURNS", "6"))
TTL_SECONDS = float(os.getenv("BHAROSHA_SESSION_TTL", "1800"))  # 30 minutes
MAX_SESSIONS = int(os.getenv("BHAROSHA_MAX_SESSIONS", "5000"))


class _Session:
    __slots__ = ("turns", "touched")

    def __init__(self) -> None:
        self.turns: deque[tuple[str, str]] = deque(maxlen=MAX_TURNS)
        self.touched = time.monotonic()


class SessionStore:
    def __init__(self) -> None:
        self._sessions: OrderedDict[str, _Session] = OrderedDict()
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        expired = [
            key
            for key, session in self._sessions.items()
            if now - session.touched > TTL_SECONDS
        ]
        for key in expired:
            del self._sessions[key]

    def history(self, session_id: str) -> list[tuple[str, str]]:
        now = time.monotonic()
        with self._lock:
            self._purge(now)
            session = self._sessions.get(session_id)
            if session is None:
                return []
            session.touched = now
            self._sessions.move_to_end(session_id)
            return list(session.turns)

    def record(self, session_id: str, question: str, answer: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._purge(now)
            session = self._sessions.get(session_id)
            if session is None:
                if len(self._sessions) >= MAX_SESSIONS:
                    self._sessions.popitem(last=False)
                session = _Session()
                self._sessions[session_id] = session
            session.turns.append((question, answer))
            session.touched = now
            self._sessions.move_to_end(session_id)

    def forget(self, session_id: str) -> None:
        """Drop a conversation on request — the app calls this on exit."""
        with self._lock:
            self._sessions.pop(session_id, None)

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)


store = SessionStore()
