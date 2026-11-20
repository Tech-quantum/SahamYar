import math
import threading
import time
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from app.errors import ProviderSchemaError, ProviderUnavailable

CODAL_SEARCH_BASE_URL = "https://search.codal.ir"
CODAL_REPORT_BASE_URL = "https://codal.ir"
CODAL_ALLOWED_HOST_SUFFIX = "codal.ir"
MAX_REPORT_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 3

_COMPANIES_PATH = "/api/search/v1/companies"
_SEARCH_PATH = "/api/search/v2/q"


def _clean_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


class CodalClient:
    """Defensive synchronous client for the public Codal search API.

    It only fetches raw data. Parsing financial statements is done by
    app.providers.codal; this class does not interpret report contents.
    """

    def __init__(
        self,
        http_client: httpx.Client | None = None,
        min_interval: float = 1.0,
        max_retries: int = 2,
        timeout: float = 20.0,
    ) -> None:
        for name, value in (("min_interval", min_interval), ("timeout", timeout)):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"{name} must be a finite non-negative number.")
        if timeout == 0:
            raise ValueError("timeout must be greater than zero.")
        if (
            isinstance(max_retries, bool)
            or not isinstance(max_retries, int)
            or max_retries < 0
        ):
            raise ValueError("max_retries must be a non-negative integer.")

        self._client = http_client
        self._owns_client = http_client is None
        self._min_interval = float(min_interval)
        self._timeout = float(timeout)
        self._max_retries = max_retries
        self._lock = threading.Lock()
        self._last_request_at = 0.0

    def start(self) -> None:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self._timeout,
                headers={
                    "Accept": "application/json, text/html, */*",
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
                    ),
                },
            )

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def _get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        allow_redirect: bool = False,
    ) -> httpx.Response:
        if self._client is None:
            self.start()
        assert self._client is not None

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                with self._lock:
                    wait_for = self._min_interval - (
                        time.monotonic() - self._last_request_at
                    )
                    if wait_for > 0:
                        time.sleep(wait_for)
                    response = self._client.get(
                        url, params=params, follow_redirects=False
                    )
                    self._last_request_at = time.monotonic()

                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt < self._max_retries:
                        time.sleep(min(2 ** attempt, 5))
                        continue

                if allow_redirect and 300 <= response.status_code < 400:
                    return response

                response.raise_for_status()
                return response
            except (httpx.HTTPError, TimeoutError) as exc:
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(min(2 ** attempt, 5))

        raise ProviderUnavailable(f"Codal request failed: {last_error}") from last_error

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self._get(f"{CODAL_SEARCH_BASE_URL}{path}", params)
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderSchemaError("Codal returned a non-JSON response.") from exc

    def get_companies(self) -> list[dict[str, Any]]:
        """Return the Codal company list (raw row preserved under 'raw')."""
        payload = self._get_json(_COMPANIES_PATH)
        if not isinstance(payload, list):
            raise ProviderSchemaError("Codal company list root must be a JSON array.")

        companies = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            symbol = _clean_str(row.get("sy"))
            if symbol is None:
                continue
            companies.append({
                "symbol": symbol,
                "name": _clean_str(row.get("n")),
                "codal_id": _clean_str(row.get("i")),
                "raw": row,
            })
        return companies

    def search_letters(
        self,
        symbol: str,
        page: int = 1,
    ) -> dict[str, Any]:
        """Search Codal letters/reports for a symbol (one page, 20 rows)."""
        symbol = _clean_str(symbol)
        if symbol is None:
            raise ValueError("symbol must be a non-empty string.")
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise ValueError("page must be a positive integer.")

        payload = self._get_json(_SEARCH_PATH, {
            "Symbol": symbol,
            "PageNumber": page,
            "Length": -1,
            "Audited": "true",
            "NotAudited": "true",
            "Childs": "true",
            "Mains": "true",
            "Consolidatable": "true",
            "NotConsolidatable": "true",
            "search": "true",
        })
        if not isinstance(payload, dict):
            raise ProviderSchemaError("Codal search root must be a JSON object.")
        letters = payload.get("Letters")
        if not isinstance(letters, list):
            raise ProviderSchemaError("Codal search response has no Letters list.")

        normalized = []
        for row in letters:
            if not isinstance(row, dict):
                continue
            normalized.append({
                "tracing_no": row.get("TracingNo"),
                "symbol": _clean_str(row.get("Symbol")),
                "company_name": _clean_str(row.get("CompanyName")),
                "title": _clean_str(row.get("Title")),
                "letter_code": _clean_str(row.get("LetterCode")),
                "sent_at": _clean_str(row.get("SentDateTime")),
                "published_at": _clean_str(row.get("PublishDateTime")),
                "has_html": bool(row.get("HasHtml")),
                "has_excel": bool(row.get("HasExcel")),
                "has_pdf": bool(row.get("HasPdf")),
                "url": _clean_str(row.get("Url")),
                "raw": row,
            })

        return {
            "total": payload.get("Total"),
            "page": payload.get("Page"),
            "letters": normalized,
        }

    @staticmethod
    def resolve_report_url(url: str) -> str:
        """Turn a letter Url into a safe absolute Codal https URL."""
        url = _clean_str(url)
        if url is None:
            raise ValueError("Report URL must be a non-empty string.")
        if any(ord(ch) < 32 for ch in url):
            raise ValueError("Report URL contains control characters.")

        absolute = urljoin(CODAL_REPORT_BASE_URL + "/", url)
        try:
            parts = urlsplit(absolute)
            hostname = (parts.hostname or "").lower().rstrip(".")
        except ValueError as exc:
            raise ValueError("Invalid report URL.") from exc

        host_ok = hostname == CODAL_ALLOWED_HOST_SUFFIX or hostname.endswith(
            "." + CODAL_ALLOWED_HOST_SUFFIX
        )
        if (
            parts.scheme != "https"
            or not host_ok
            or parts.username is not None
            or parts.password is not None
        ):
            raise ValueError("Report URL must be an https codal.ir address.")
        return absolute

    def get_report_html(self, url: str) -> str:
        """Fetch the HTML of one report; the URL comes from search_letters."""
        current = self.resolve_report_url(url)
        for _ in range(MAX_REDIRECTS + 1):
            response = self._get(current, allow_redirect=True)
            if not 300 <= response.status_code < 400:
                break
            location = response.headers.get("location")
            if not location:
                raise ProviderSchemaError("Codal redirect has no Location header.")
            current = self.resolve_report_url(urljoin(current, location))
        else:
            raise ProviderSchemaError("Codal report redirected too many times.")
        if len(response.content) > MAX_REPORT_BYTES:
            raise ProviderSchemaError("Codal report is larger than the allowed size.")
        text = response.text
        if not text.strip():
            raise ProviderSchemaError("Codal returned an empty report.")
        return text
