import logging
import threading
import time
from typing import Any, Callable

from app.price_service import PRIORITY_INTERVALS, PRIORITY_ORDER

logger = logging.getLogger(__name__)


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

        for code in symbols:
            self._next_due.setdefault(code, now)

        # Remove scheduling state for symbols no longer tracked.
        tracked = set(symbols)
        for code in tuple(self._next_due):
            if code not in tracked:
                self._next_due.pop(code, None)

        due = [
            code for code in symbols
            if self._next_due.get(code, float("inf")) <= now
        ]
        if not due:
            return None

        # Earlier deadlines win; priority breaks ties.
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

        try:
            self.price_service.get_price(code, force_refresh=True, priority=None)
        except Exception:
            logger.exception("Price refresh failed for instrument %s", code)
        finally:
            self._next_due[code] = now + self._interval_for(
                code, status.interval_seconds
            )

        return code

    def seconds_until_next_due(self) -> float | None:
        if not self._next_due:
            return None
        return max(0.0, min(self._next_due.values()) - self._clock())

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
                logger.exception("Price refresh failed for instrument %s", code)
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
                        # One upstream request per scheduler turn.
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
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="sahamyar-price-refresh",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()

        with self._lock:
            thread = self._thread

        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
