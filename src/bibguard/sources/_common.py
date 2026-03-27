"""Shared utilities for API sources."""

from __future__ import annotations

import threading
import time

HEADERS = {"User-Agent": "bibguard/1.0 (academic citation verifier; https://github.com/GeoffreyWang1117/bibguard)"}

_last_call: dict[str, float] = {}
_locks: dict[str, threading.Lock] = {}
_global_lock = threading.Lock()
RATE_LIMITS = {"arxiv": 3.0, "crossref": 1.0, "dblp": 1.0, "s2": 1.0, "openalex": 0.5}


def _get_lock(source: str) -> threading.Lock:
    """Get or create a per-source lock (thread-safe)."""
    if source not in _locks:
        with _global_lock:
            if source not in _locks:
                _locks[source] = threading.Lock()
    return _locks[source]


def rate_limit(source: str) -> None:
    """Thread-safe per-source rate limiting."""
    lock = _get_lock(source)
    with lock:
        now = time.time()
        delay = RATE_LIMITS.get(source, 1.0)
        last = _last_call.get(source, 0)
        wait = delay - (now - last)
        if wait > 0:
            time.sleep(wait)
        _last_call[source] = time.time()
