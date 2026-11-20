import copy
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from app.errors import ProviderSchemaError, ProviderUnavailable
from app.market_hours import MarketHours


PRIORITY_INTERVALS = {
    "alert": 20,
    "watchlist": 60,
    "background": 180,
}

PRIORITY_ORDER = {
    "alert": 0,
    "watchlist": 1,
    "background": 2,
}


@dataclass(frozen=True)
class PriceCacheEntry:
    item: dict[str, Any]
    fetched_at: str
    fetched_monotonic: float


class PriceDataService:
    """Shared price cache with source-based symbol subscriptions."""

    def __init__(
        self,
        provider: Any,
        market_hours: MarketHours | None = None,
        clock: Callable[[], float] = time.monotonic,
        utcnow: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.provider = provider
        self.market_hours = market_hours or MarketHours()
        self._clock = clock
        self._utcnow = utcnow
        self._cache: dict[str, PriceCacheEntry] = {}
        self._symbol_locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()
        self._symbol_usages: dict[str, set[str]] = {}

    def _get_symbol_lock(self, ins_code: str) -> threading.Lock:
        with self._guard:
            lock = self._symbol_locks.get(ins_code)
            if lock is None:
                lock = threading.Lock()
                self._symbol_locks[ins_code] = lock
            return lock

    def register_symbol(
        self,
        ins_code: str,
        priority: str = "watchlist",
        source: str | None = None,
    ) -> None:
        code = ins_code.strip()
        if not code:
            raise ValueError("A non-empty instrument code is required.")
        if priority not in PRIORITY_INTERVALS:
            raise ValueError(f"Unsupported symbol priority: {priority}")

        usage = source or priority
        if usage not in PRIORITY_INTERVALS:
            raise ValueError(f"Unsupported symbol source: {usage}")

        with self._guard:
            self._symbol_usages.setdefault(code, set()).add(usage)

    def unregister_symbol(self, ins_code: str, source: str) -> bool:
        """Remove one source subscription; return whether the symbol is untracked."""
        code = ins_code.strip()
        if not code:
            raise ValueError("A non-empty instrument code is required.")
        if source not in PRIORITY_INTERVALS:
            raise ValueError(f"Unsupported symbol source: {source}")

        with self._guard:
            usages = self._symbol_usages.get(code)
            if usages is None:
                return True

            usages.discard(source)
            if not usages:
                self._symbol_usages.pop(code, None)
                return True
            return False

    def tracked_symbols(self) -> tuple[str, ...]:
        with self._guard:
            return tuple(sorted(self._symbol_usages))

    def symbol_sources(self, ins_code: str) -> tuple[str, ...]:
        with self._guard:
            return tuple(sorted(self._symbol_usages.get(ins_code, ())))

    def symbol_priority(self, ins_code: str) -> str:
        with self._guard:
            usages = self._symbol_usages.get(ins_code)
            if not usages:
                return "background"
            return min(usages, key=lambda item: PRIORITY_ORDER[item])

    def get_price(
        self,
        ins_code: str,
        force_refresh: bool = False,
        priority: str | None = None,
    ) -> dict[str, Any]:
        code = ins_code.strip()
        if not code:
            raise ValueError("A non-empty instrument code is required.")

        # Explicit priority means an intentional subscription.
        # Ordinary detail/API requests remain temporary and do not track symbols.
        if priority is not None:
            self.register_symbol(code, priority, source=priority)

        status = self.market_hours.get_status()
        symbol_interval = max(
            status.interval_seconds,
            PRIORITY_INTERVALS[self.symbol_priority(code)],
        )
        lock = self._get_symbol_lock(code)

        with lock:
            cached = self._cache.get(code)
            age = (
                self._clock() - cached.fetched_monotonic
                if cached is not None else None
            )

            if (
                cached is not None
                and not force_refresh
                and age is not None
                and age < symbol_interval
            ):
                return self._response(code, cached, status, "fresh")

            try:
                item = self.provider.get_closing_price_info(code)
            except (ProviderUnavailable, ProviderSchemaError) as exc:
                if cached is None:
                    raise
                return self._response(
                    code, cached, status, "stale", last_error=str(exc)
                )

            entry = PriceCacheEntry(
                item=copy.deepcopy(item),
                fetched_at=self._utcnow().isoformat(),
                fetched_monotonic=self._clock(),
            )
            self._cache[code] = entry
            return self._response(code, entry, status, "fresh")

    @staticmethod
    def _response(
        ins_code: str,
        entry: PriceCacheEntry,
        status: Any,
        data_status: str,
        last_error: str | None = None,
    ) -> dict[str, Any]:
        result = {
            "source": "TSETMC",
            "ins_code": ins_code,
            "item": copy.deepcopy(entry.item),
            "retrieved_at": entry.fetched_at,
            "data_status": data_status,
            "market_phase": status.phase,
            "refresh_interval_seconds": status.interval_seconds,
        }
        if last_error is not None:
            result["last_error"] = last_error
        return result
