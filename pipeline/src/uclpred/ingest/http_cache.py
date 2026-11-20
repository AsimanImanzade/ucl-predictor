"""Tiny on-disk HTTP cache."""

import time
from pathlib import Path

import requests

_last_request_at = 0.0


def get_cached(
    url: str,
    cache_path: Path,
    headers: dict | None = None,
    min_interval_s: float = 0.0,
) -> bytes:
    """Return cached bytes if present, otherwise download, write and return them.

    Raises requests.HTTPError for non-2xx (including 404); nothing is cached then.
    """
    global _last_request_at
    cache_path = Path(cache_path)
    if cache_path.exists():
        return cache_path.read_bytes()
    wait = min_interval_s - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    try:
        resp = requests.get(url, headers=headers, timeout=30)
    finally:
        _last_request_at = time.monotonic()
    resp.raise_for_status()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(resp.content)
    return resp.content
