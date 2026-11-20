from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo


TEHRAN = ZoneInfo("Asia/Tehran")


@dataclass(frozen=True)
class MarketStatus:
    phase: str
    interval_seconds: int
    is_trading_day: bool
    local_time: str


class MarketHours:
    """Trading schedule for Iranian listed shares and rights."""

    def __init__(self, holidays: set[date] | None = None):
        self.holidays = holidays or set()

    def get_status(self, now: datetime | None = None) -> MarketStatus:
        current = now or datetime.now(TEHRAN)

        if current.tzinfo is None:
            current = current.replace(tzinfo=TEHRAN)
        else:
            current = current.astimezone(TEHRAN)

        trading_day = current.weekday() in (5, 6, 0, 1, 2)
        trading_day = trading_day and current.date() not in self.holidays
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
        )
