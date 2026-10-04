"""Cliente HTTP con caché en disco, rate limiting y modo offline."""

import hashlib
import json
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

USER_AGENT = "authors-db/0.1 (https://github.com/Quikebarre/authors-db; technical-test)"


class OfflineCacheMissError(RuntimeError):
    """Se pidió una URL que no está en caché estando en modo offline."""


class CachedClient:
    """GET JSON con caché de respuestas crudas (url, params, retrieved_at, response)."""

    def __init__(
        self,
        cache_dir: Path,
        offline: bool = False,
        min_interval_s: float = 0.2,
        timeout_s: float = 30.0,
    ) -> None:
        self._cache_dir = cache_dir
        self._offline = offline
        self._min_interval_s = min_interval_s
        self._lock = threading.Lock()
        self._next_slot = 0.0
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=timeout_s, follow_redirects=True
        )
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, url: str, params: dict[str, Any]) -> Path:
        raw = json.dumps([url, sorted(params.items())], ensure_ascii=False)
        return self._cache_dir / f"{hashlib.sha256(raw.encode()).hexdigest()[:24]}.json"

    def _wait_for_slot(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next_slot - now
            self._next_slot = max(now, self._next_slot) + self._min_interval_s
        if wait > 0:
            time.sleep(wait)

    def get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """Devuelve la respuesta JSON, desde caché si existe."""
        path = self._cache_path(url, params)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["response"]
        if self._offline:
            raise OfflineCacheMissError(f"{url} {params}")
        response = self._get_with_retry(url, params)
        record = {
            "url": url,
            "params": params,
            "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "response": response,
        }
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        return response

    def _get_with_retry(self, url: str, params: dict[str, Any], attempts: int = 4) -> Any:
        for attempt in range(attempts):
            self._wait_for_slot()
            try:
                resp = self._client.get(url, params=params)
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                    time.sleep(2**attempt)
                    continue
                resp.raise_for_status()
                return resp.json()
            except httpx.TransportError:
                if attempt == attempts - 1:
                    raise
                time.sleep(2**attempt)
        raise RuntimeError("unreachable")
