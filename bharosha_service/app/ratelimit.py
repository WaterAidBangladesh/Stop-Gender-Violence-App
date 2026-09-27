"""Rate limiting for cost and abuse control. Not a security boundary.

The endpoint is deliberately open — requiring an account to ask for help is a
barrier at the worst possible moment — so something has to bound what an
unauthenticated caller can spend on model calls.

BEHIND RENDER'S PROXY the socket address is the proxy, not the caller. Reading
it would make every request look like one client, and the limiter would then
either throttle everybody or nobody. The caller's address arrives in
X-Forwarded-For instead, as a list: `client, proxy1, proxy2`.

Which entry to trust: a client can send its own X-Forwarded-For, and the proxy
appends rather than replaces, so the leftmost entries are attacker-controlled
and the rightmost are the ones our own infrastructure observed. This takes the
entry TRUSTED_PROXY_HOPS from the right — 1 for a single Render proxy. Add a hop
if you put a CDN in front, or the limiter will key on the CDN's address.

Even done correctly this is spoofable enough that it is a cost control and
nothing more: anyone willing to rotate addresses gets through. It must never be
the reason something is considered secure, and emergency referrals are served
without consulting it at all — they cost nothing and a person in danger is never
rate limited.
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict

# A conversation is a handful of messages a minute. Burst covers someone typing
# quickly or retrying; the sustained rate is what bounds spend.
BURST = int(os.getenv("BHAROSHA_RATE_BURST", "5"))
PER_MINUTE = float(os.getenv("BHAROSHA_RATE_PER_MINUTE", "12"))

# Ceiling across all callers, so a distributed flood cannot run up a bill.
GLOBAL_PER_MINUTE = float(os.getenv("BHAROSHA_GLOBAL_PER_MINUTE", "240"))
GLOBAL_BURST = int(os.getenv("BHAROSHA_GLOBAL_BURST", "60"))

TRUSTED_PROXY_HOPS = int(os.getenv("BHAROSHA_TRUSTED_PROXY_HOPS", "1"))

# Bounded so the limiter itself cannot be used to exhaust memory.
MAX_TRACKED = int(os.getenv("BHAROSHA_RATE_MAX_TRACKED", "10000"))


def client_key(forwarded_for: str | None, socket_host: str | None) -> str:
    """The address to key on, taken TRUSTED_PROXY_HOPS from the right."""
    if forwarded_for:
        hops = [part.strip() for part in forwarded_for.split(",") if part.strip()]
        if hops:
            index = max(0, len(hops) - TRUSTED_PROXY_HOPS)
            return hops[index]
    return socket_host or "unknown"


class _Bucket:
    __slots__ = ("tokens", "updated")

    def __init__(self, tokens: float) -> None:
        self.tokens = tokens
        self.updated = time.monotonic()


class TokenBucket:
    """Classic token bucket, one per caller plus one global."""

    def __init__(self, burst: int, per_minute: float) -> None:
        self.burst = float(burst)
        self.per_second = per_minute / 60.0
        self._buckets: OrderedDict[str, _Bucket] = OrderedDict()
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= MAX_TRACKED:
                    # Evict the least recently seen caller, not the newest.
                    self._buckets.popitem(last=False)
                bucket = _Bucket(self.burst)
                self._buckets[key] = bucket
            else:
                self._buckets.move_to_end(key)
                elapsed = now - bucket.updated
                bucket.tokens = min(self.burst, bucket.tokens + elapsed * self.per_second)
            bucket.updated = now

            if bucket.tokens < 1.0:
                return False
            bucket.tokens -= 1.0
            return True


_per_client = TokenBucket(BURST, PER_MINUTE)
_global = TokenBucket(GLOBAL_BURST, GLOBAL_PER_MINUTE)


def allow(key: str) -> bool:
    """True if this caller may consume a model call right now."""
    if not _global.allow("*"):
        return False
    return _per_client.allow(key)
