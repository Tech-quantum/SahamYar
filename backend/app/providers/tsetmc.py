import copy
import math
import re
import threading
import time
from collections import OrderedDict
from datetime import datetime
from typing import Any
from urllib.parse import quote, unquote, urlsplit

import httpx

from app.config import settings
from app.errors import ProviderSchemaError, ProviderUnavailable


def _finite_number(value: Any) -> float | None:
    """Parse a finite numeric value without accepting booleans or invalid data."""
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", "")
            if not value:
                return None
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


class TsetmcClient:
    """Defensive synchronous client for TSETMC public JSON API."""

    def __init__(
        self,
        http_client: httpx.Client | None = None,
        min_interval: float | None = None,
        max_retries: int | None = None,
        history_cache_ttl: float = 60.0,
        history_cache_max_entries: int = 100,
    ) -> None:
        self._client = http_client
        self._owns_client = http_client is None
        effective_interval = (
            settings.tsetmc_min_interval_seconds
            if min_interval is None else min_interval
        )
        effective_retries = (
            settings.tsetmc_max_retries
            if max_retries is None else max_retries
        )

        for name, value in (
            ("min_interval", effective_interval),
            ("history_cache_ttl", history_cache_ttl),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"{name} must be a finite non-negative number.")

        if (
            isinstance(effective_retries, bool)
            or not isinstance(effective_retries, int)
            or effective_retries < 0
        ):
            raise ValueError("max_retries must be a non-negative integer.")

        if (
            isinstance(history_cache_max_entries, bool)
            or not isinstance(history_cache_max_entries, int)
            or history_cache_max_entries < 1
        ):
            raise ValueError("history_cache_max_entries must be a positive integer.")

        self._min_interval = float(effective_interval)
        self._max_retries = effective_retries
        self._lock = threading.Lock()
        self._last_request_at = 0.0
        self._history_cache_ttl = float(history_cache_ttl)
        self._history_cache_max_entries = history_cache_max_entries
        self._history_cache: OrderedDict[
            str, tuple[float, list[dict[str, Any]]]
        ] = OrderedDict()
        self._history_cache_lock = threading.Lock()
        self._history_key_locks: dict[str, tuple[threading.Lock, int]] = {}

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
            )

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def _get_json(self, path: str) -> dict[str, Any]:
        if not isinstance(path, str) or not path:
            raise ValueError("TSETMC request path must be a non-empty string.")

        if (
            path.startswith(("/", "\\"))
            or any(char.isspace() or ord(char) < 32 for char in path)
        ):
            raise ValueError("TSETMC request path must be a safe relative path.")

        try:
            parsed_path = urlsplit(path)
        except ValueError as exc:
            raise ValueError("Invalid TSETMC request path.") from exc

        if (
            parsed_path.scheme
            or parsed_path.netloc
            or parsed_path.query
            or parsed_path.fragment
        ):
            raise ValueError("TSETMC request path must not contain a URL or query.")

        decoded_path = unquote(path)

        if (
            decoded_path.startswith(("/", "\\"))
            or "\\" in decoded_path
            or "?" in decoded_path
            or "#" in decoded_path
            or any(char.isspace() or ord(char) < 32 for char in decoded_path)
            or any(part in (".", "..") for part in decoded_path.split("/"))
        ):
            raise ValueError("TSETMC request path contains unsafe path segments.")

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

                    response = self._client.get(url, follow_redirects=False)
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

    @staticmethod
    def _classify_instrument(row: dict[str, Any]) -> tuple[str | None, str, str]:
        """Classify instruments while retaining unknown TSETMC categories."""
        raw_type = row.get("cgrValCot")
        instrument_type = (
            str(raw_type).strip().upper() if raw_type is not None else None
        )
        instrument_type = instrument_type or None

        name = str(row.get("lVal30") or "")
        normalized_name = (
            name.replace("\u200c", " ")
                .replace("\u200f", "")
                .replace("\u200e", "")
                .replace("\xa0", " ")
                .strip()
        )

        if re.match(r"^(?:ح\s*\.?\s*|حق\s*تقدم)", normalized_name):
            return instrument_type, "RIGHTS", "حق‌تقدم"
        if instrument_type in {"N1", "N2", "Z1"}:
            return instrument_type, "COMMON_STOCK", "سهام"
        if instrument_type in {"H1", "51"}:
            return instrument_type, "FUND", "صندوق"
        if instrument_type == "17":
            return instrument_type, "DEBT", "اوراق بدهی"
        return instrument_type, "OTHER", "سایر"

    def search_instruments(self, query: str) -> list[dict[str, Any]]:
        normalized_query = (
            query.strip()
            .replace("ی", "ي")
            .replace("ک", "ك")
        )
        encoded_query = quote(normalized_query, safe="")
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

            instrument_type, category, category_label = (
                self._classify_instrument(row)
            )
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
                "instrument_type": instrument_type,
                "instrument_category": category,
                "instrument_category_label": category_label,
                "raw": row,
            })

        return normalized

    def get_instrument_info(self, ins_code: str) -> dict[str, Any]:
        """Fetch and normalize detailed information for one instrument."""
        payload = self._get_json(
            f"Instrument/GetInstrumentInfo/{quote(ins_code.strip(), safe='')}"
        )
        info = payload.get("instrumentInfo")

        if not isinstance(info, dict):
            raise ProviderSchemaError(
                "Expected 'instrumentInfo' object in TSETMC response."
            )

        sector = info.get("sector")
        eps = info.get("eps")
        eps_data = eps if isinstance(eps, dict) else {}
        fundamentals = {
            "eps_actual": _finite_number(eps_data.get("epsValue")),
            "eps_estimated": _finite_number(eps_data.get("estimatedEPS")),
            "sector_pe": _finite_number(eps_data.get("sectorPE")),
        }
        instrument_type, category, category_label = (
            self._classify_instrument(info)
        )

        average_volume_raw = info.get("qTotTran5JAvg")
        average_volume = None
        if isinstance(average_volume_raw, int) and not isinstance(average_volume_raw, bool):
            average_volume = average_volume_raw if average_volume_raw >= 0 else None
        elif isinstance(average_volume_raw, float):
            if average_volume_raw >= 0 and average_volume_raw.is_integer():
                average_volume = int(average_volume_raw)

        return {
            "ins_code": (
                str(info["insCode"])
                if info.get("insCode") is not None else None
            ),
            "symbol": info.get("lVal18AFC"),
            "name": info.get("lVal30"),
            "isin": info.get("cIsin"),
            "market_flow": info.get("flow"),
            "market": info.get("flowTitle"),
            "instrument_type": instrument_type,
            "instrument_category": category,
            "instrument_category_label": category_label,
            "sector": (
                sector.get("lSecVal")
                if isinstance(sector, dict) else None
            ),
            "eps": eps_data,
            "fundamentals": fundamentals,
            "shares_count": info.get("zTitad"),
            "average_volume": average_volume,
            "base_volume": info.get("baseVol"),
            "min_week": info.get("minWeek"),
            "max_week": info.get("maxWeek"),
            "min_year": info.get("minYear"),
            "max_year": info.get("maxYear"),
            "raw": info,
        }

    def get_closing_price_info(self, ins_code: str) -> dict[str, Any]:
        """Fetch the latest trading and closing price information."""
        payload = self._get_json(
            f"ClosingPrice/GetClosingPriceInfo/{quote(ins_code.strip(), safe='')}"
        )
        info = payload.get("closingPriceInfo")

        if not isinstance(info, dict):
            raise ProviderSchemaError(
                "Expected 'closingPriceInfo' object in TSETMC response."
            )

        state = info.get("instrumentState")

        return {
            "ins_code": ins_code.strip(),
            "date": info.get("finalLastDate"),
            "closing_price": info.get("pClosing"),
            "last_price": info.get("pDrCotVal"),
            "first_price": info.get("priceFirst"),
            "min_price": info.get("priceMin"),
            "max_price": info.get("priceMax"),
            "yesterday_price": info.get("priceYesterday"),
            "trade_count": info.get("zTotTran"),
            "volume": info.get("qTotTran5J"),
            "value": info.get("qTotCap"),
            "state": (
                state.get("cEtavalTitle")
                if isinstance(state, dict) else None
            ),
            "raw": info,
        }

    def get_daily_prices(
        self,
        ins_code: str,
        count: int = 30,
    ) -> list[dict[str, Any]]:
        """Return recent daily prices using a short-lived per-symbol cache."""
        if not 1 <= count <= 365:
            raise ValueError("Daily price count must be between 1 and 365.")

        if not isinstance(ins_code, str) or not ins_code.strip():
            raise ValueError("A non-empty instrument code is required.")

        code = ins_code.strip()

        def cached_history():
            if self._history_cache_ttl == 0:
                return None
            with self._history_cache_lock:
                entry = self._history_cache.get(code)
                if entry is None:
                    return None
                expires_at, rows = entry
                if time.monotonic() >= expires_at:
                    del self._history_cache[code]
                    return None
                self._history_cache.move_to_end(code)
                return rows

        cached = cached_history()
        if cached is not None:
            return copy.deepcopy(cached[-count:])

        with self._history_cache_lock:
            entry = self._history_key_locks.get(code)
            if entry is None:
                key_lock = threading.Lock()
                self._history_key_locks[code] = (key_lock, 1)
            else:
                key_lock, users = entry
                self._history_key_locks[code] = (key_lock, users + 1)

        try:
            with key_lock:
                cached = cached_history()
                if cached is not None:
                    return copy.deepcopy(cached[-count:])

                payload = self._get_json(
                    f"ClosingPrice/GetClosingPriceDailyList/"
                    f"{quote(code, safe='')}/365"
                )
                rows = payload.get("closingPriceDaily")

                if not isinstance(rows, list):
                    raise ProviderSchemaError(
                        "Expected 'closingPriceDaily' list in TSETMC response."
                    )

                dated: dict[int, dict[str, Any]] = {}

                for row in rows:
                    if not isinstance(row, dict):
                        continue

                    item = {
                        "date": row.get("dEven"),
                        "change": row.get("priceChange"),
                        "closing_price": row.get("pClosing"),
                        "last_price": row.get("pDrCotVal"),
                        "first_price": row.get("priceFirst"),
                        "min_price": row.get("priceMin"),
                        "max_price": row.get("priceMax"),
                        "yesterday_price": row.get("priceYesterday"),
                        "trade_count": row.get("zTotTran"),
                        "volume": row.get("qTotTran5J"),
                        "value": row.get("qTotCap"),
                        "raw": row,
                    }

                    date_text = (
                        str(item["date"]).strip()
                        if item["date"] is not None else ""
                    )
                    if len(date_text) != 8 or not date_text.isdigit():
                        continue

                    try:
                        date_key = int(date_text)
                        datetime.strptime(date_text, "%Y%m%d")
                    except ValueError:
                        continue

                    dated[date_key] = item

                ordered = [dated[key] for key in sorted(dated)]

                if self._history_cache_ttl > 0:
                    with self._history_cache_lock:
                        self._history_cache[code] = (
                            time.monotonic() + self._history_cache_ttl,
                            ordered,
                        )
                        self._history_cache.move_to_end(code)
                        while len(self._history_cache) > self._history_cache_max_entries:
                            self._history_cache.popitem(last=False)

                return copy.deepcopy(ordered[-count:])
        finally:
            with self._history_cache_lock:
                current_lock, users = self._history_key_locks[code]
                if users == 1:
                    del self._history_key_locks[code]
                else:
                    self._history_key_locks[code] = (current_lock, users - 1)
