from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.market_calendar import MarketCalendar, current_jalali_year


TEHRAN = ZoneInfo("Asia/Tehran")


@dataclass(frozen=True)
class MarketStatus:
    phase: str
    interval_seconds: int
    is_trading_day: bool
    local_time: str
    calendar_status: str | None = None
    calendar_warnings: tuple[str, ...] = ()


class MarketHours:
    """Trading schedule for Iranian listed shares and rights."""

    def __init__(
        self,
        holidays: set[date] | None = None,
        *,
        calendar: MarketCalendar | None = None,
        require_calendar: bool = False,
        calendar_error: str | None = None,
    ):
        if calendar is not None and not isinstance(calendar, MarketCalendar):
            raise TypeError("calendar must be a MarketCalendar instance.")
        if not isinstance(require_calendar, bool):
            raise TypeError("require_calendar must be a boolean.")
        if calendar_error is not None and (
            not isinstance(calendar_error, str) or not calendar_error.strip()
        ):
            raise ValueError("calendar_error must be a non-empty string.")

        self.holidays = set(holidays or ())
        self.calendar = calendar
        self.require_calendar = require_calendar
        self.calendar_error = calendar_error

    @staticmethod
    def _closed(current: datetime, calendar_status: str) -> MarketStatus:
        return MarketStatus(
            phase="closed",
            interval_seconds=3600,
            is_trading_day=False,
            local_time=current.isoformat(),
            calendar_status=calendar_status,
        )

    def get_status(self, now: datetime | None = None) -> MarketStatus:
        current = now or datetime.now(TEHRAN)

        if current.tzinfo is None:
            current = current.replace(tzinfo=TEHRAN)
        else:
            current = current.astimezone(TEHRAN)

        calendar_day_status = None
        calendar_status = None
        calendar_warnings: tuple[str, ...] = ()

        if self.calendar_error is not None:
            return self._closed(current, "invalid")

        if self.require_calendar and self.calendar is None:
            return self._closed(current, "needs_update")

        if self.calendar is not None:
            expected_year = current_jalali_year(current)
            if self.calendar.jalali_year != expected_year:
                return self._closed(current, "needs_update")

            try:
                calendar_day_status = self.calendar.get_status(
                    current.date(),
                    now=current,
                )
            except Exception:
                return self._closed(current, "invalid")

            calendar_status = calendar_day_status.status
            calendar_warnings = tuple(
                event.title for event in calendar_day_status.warnings
            )

        trading_day = current.weekday() in (5, 6, 0, 1, 2)
        trading_day = trading_day and current.date() not in self.holidays

        if calendar_day_status is not None:
            trading_day = trading_day and not calendar_day_status.is_closed

        current_time = current.time().replace(tzinfo=None)

        if not trading_day:
            phase, interval = "closed", 3600
        elif time(8, 45) <= current_time < time(9, 0):
            phase, interval = "pre_open", 60
        elif time(9, 0) <= current_time < time(12, 30):
            phase, interval = "continuous", 20
        elif time(12, 30) <= current_time < time(13, 0):
            phase, interval = "post_market", 300
        else:
            phase, interval = "closed", 3600

        return MarketStatus(
            phase=phase,
            interval_seconds=interval,
            is_trading_day=trading_day,
            local_time=current.isoformat(),
            calendar_status=calendar_status,
            calendar_warnings=calendar_warnings,
        )
