import threading
import time
from typing import Any
from urllib.parse import quote

import httpx

from app.config import settings
from app.errors import ProviderSchemaError, ProviderUnavailable


class TsetmcClient:
    """Defensive synchronous client for TSETMC public JSON API."""

    def __init__(
        self,
        http_client: httpx.Client | None = None,
        min_interval: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self._client = http_client
        self._owns_client = http_client is None
        self._min_interval = (
            settings.tsetmc_min_interval_seconds
            if min_interval is None else min_interval
        )
        self._max_retries = (
            settings.tsetmc_max_retries
            if max_retries is None else max_retries
        )
        self._lock = threading.Lock()
        self._last_request_at = 0.0

    def start(self) -> None:
        if self._client is None:
            self._client = httpx.Client(
                timeout=settings.tsetmc_timeout_seconds,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
                    ),
                },
                follow_redirects=True,
            )

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def _get_json(self, path: str) -> dict[str, Any]:
        if self._client is None:
            self.start()

        assert self._client is not None
        url = f"{settings.tsetmc_base_url.rstrip('/')}/{path.lstrip('/')}"
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                with self._lock:
                    wait_for = self._min_interval - (
                        time.monotonic() - self._last_request_at
                    )
                    if wait_for > 0:
                        time.sleep(wait_for)

                    response = self._client.get(url)
                    self._last_request_at = time.monotonic()

                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt < self._max_retries:
                        time.sleep(min(2 ** attempt, 5))
                        continue

                response.raise_for_status()

                try:
                    payload = response.json()
                except ValueError as exc:
                    raise ProviderSchemaError(
                        "TSETMC returned a non-JSON response."
                    ) from exc

                if not isinstance(payload, dict):
                    raise ProviderSchemaError(
                        "TSETMC response root must be a JSON object."
                    )

                return payload

            except ProviderSchemaError:
                raise
            except (httpx.HTTPError, TimeoutError) as exc:
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(min(2 ** attempt, 5))

        raise ProviderUnavailable(
            f"TSETMC request failed: {last_error}"
        ) from last_error

    def search_instruments(self, query: str) -> list[dict[str, Any]]:
        encoded_query = quote(query.strip(), safe="")
        payload = self._get_json(
            f"Instrument/GetInstrumentSearch/{encoded_query}"
        )
        rows = payload.get("instrumentSearch")

        if not isinstance(rows, list):
            raise ProviderSchemaError(
                "Expected 'instrumentSearch' list in TSETMC response."
            )

        normalized = []

        for row in rows:
            if not isinstance(row, dict):
                continue

            normalized.append({
                "ins_code": (
                    str(row["insCode"])
                    if row.get("insCode") is not None else None
                ),
                "symbol": row.get("lVal18AFC"),
                "name": row.get("lVal30"),
                "isin": row.get("cIsin"),
                "market_flow": row.get("flow"),
                "market": row.get("flowTitle"),
                "raw": row,
            })

        return normalized
