import logging
import threading
import time
from typing import Any, Callable

from app.price_service import PRIORITY_INTERVALS, PRIORITY_ORDER

logger = logging.getLogger(__name__)

RETRY_DELAY_SECONDS = 5


class PriceRefreshScheduler:
    """Refresh due symbols independently, honoring their priorities."""

    def __init__(
        self,
        price_service: Any,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.price_service = price_service
        self.market_hours = price_service.market_hours
        self._clock = clock
        self._next_due: dict[str, float] = {}
        self._in_flight: set[str] = set()
        self._schedule_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _interval_for(self, code: str, market_interval: int) -> int:
        priority = self.price_service.symbol_priority(code)
        priority_interval = PRIORITY_INTERVALS.get(priority, 60)
        return max(market_interval, priority_interval)

    def refresh_due_once(self) -> str | None:
        """Refresh one due symbol; return its code, or None if none is due."""
        status = self.market_hours.get_status()
        if status.phase == "closed":
            return None

        now = self._clock()
        symbols = self.price_service.tracked_symbols()
        tracked = set(symbols)

        with self._schedule_lock:
            for code in symbols:
                self._next_due.setdefault(code, now)

            for code in tuple(self._next_due):
                if code not in tracked and code not in self._in_flight:
                    self._next_due.pop(code, None)

            due = [
                code for code in symbols
                if code not in self._in_flight
                and self._next_due.get(code, float("inf")) <= now
            ]
            if not due:
                return None

            code = min(
                due,
                key=lambda item: (
                    self._next_due[item],
                    PRIORITY_ORDER.get(
                        self.price_service.symbol_priority(item), 2
                    ),
                    item,
                ),
            )
            self._in_flight.add(code)

        # Never hold the scheduling lock during an upstream/network request.
        refresh_failed = False
        try:
            result = self.price_service.get_price(
                code, force_refresh=True, priority=None
            )
            refresh_failed = (
                isinstance(result, dict)
                and result.get("data_status") == "stale"
            )
            if refresh_failed:
                logger.warning(
                    "Price refresh returned stale cached data for instrument %s",
                    code,
                )
        except Exception:
            refresh_failed = True
            logger.exception(
                "Price refresh failed for instrument %s", code
            )
        finally:
            completed_at = self._clock()
            with self._schedule_lock:
                self._in_flight.discard(code)
                current_symbols = set(self.price_service.tracked_symbols())
                if code in current_symbols:
                    interval = self._interval_for(
                        code, status.interval_seconds
                    )
                    delay = (
                        min(RETRY_DELAY_SECONDS, interval)
                        if refresh_failed else interval
                    )
                    self._next_due[code] = completed_at + delay
                else:
                    self._next_due.pop(code, None)

        return code

    def seconds_until_next_due(self) -> float | None:
        with self._schedule_lock:
            deadlines = [
                deadline
                for code, deadline in self._next_due.items()
                if code not in self._in_flight
            ]
        if not deadlines:
            return None
        return max(0.0, min(deadlines) - self._clock())

    def refresh_once(self) -> int:
        """Force-refresh all tracked symbols; retained for manual operations/tests."""
        refreshed = 0
        for code in self.price_service.tracked_symbols():
            try:
                self.price_service.get_price(
                    code, force_refresh=True, priority=None
                )
                refreshed += 1
            except Exception:
                logger.exception(
                    "Price refresh failed for instrument %s", code
                )
        return refreshed

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                status = self.market_hours.get_status()

                if status.phase == "closed":
                    wait_seconds = min(status.interval_seconds, 60)
                else:
                    refreshed_code = self.refresh_due_once()
                    if refreshed_code is not None:
                        wait_seconds = 0
                    else:
                        remaining = self.seconds_until_next_due()
                        wait_seconds = min(
                            remaining if remaining is not None else 1.0,
                            1.0,
                        )
            except Exception:
                logger.exception("Price scheduler loop failed")
                wait_seconds = 1.0

            self._stop_event.wait(max(0.05, wait_seconds))

    def start(self) -> None:
        """Start at most one worker thread; safe to call repeatedly."""
        with self._lock:
            if self._thread is not None:
                if self._thread.is_alive():
                    return
                self._thread = None

            self._stop_event.clear()
            thread = threading.Thread(
                target=self._run,
                name="sahamyar-price-refresh",
                daemon=True,
            )
            self._thread = thread

            try:
                thread.start()
            except Exception:
                self._thread = None
                self._stop_event.set()
                raise

    def stop(self, timeout: float = 5.0) -> None:
        """Request shutdown and wait up to timeout without spawning duplicates."""
        if timeout < 0:
            raise ValueError("timeout must be non-negative")

        with self._lock:
            self._stop_event.set()
            thread = self._thread

        if thread is None or thread is threading.current_thread():
            return

        thread.join(timeout=timeout)

        with self._lock:
            if self._thread is thread and not thread.is_alive():
                self._thread = None
