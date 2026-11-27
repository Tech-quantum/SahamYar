"""Validated calendar data and scoped market-closure events."""

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from persiantools.jdatetime import JalaliDate


class CalendarDataError(ValueError):
    """Raised when calendar data is malformed or incomplete."""


TEHRAN = ZoneInfo("Asia/Tehran")


def jalali_year_for_date(day: date) -> int:
    """Return the Jalali year for a Gregorian date."""
    if isinstance(day, datetime) or not isinstance(day, date):
        raise CalendarDataError("day must be a date, not a datetime.")
    return JalaliDate.to_jalali(day.year, day.month, day.day).year


def current_jalali_year(now: datetime | None = None) -> int:
    """Return the current Jalali year using Tehran local time."""
    if now is None:
        current = datetime.now(TEHRAN)
    else:
        if not isinstance(now, datetime):
            raise CalendarDataError("now must be a datetime.")
        if now.tzinfo is None or now.utcoffset() is None:
            raise CalendarDataError("now must include a timezone.")
        current = now.astimezone(TEHRAN)

    return jalali_year_for_date(current.date())


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CalendarDataError(f"{field} must be a non-empty string.")
    return value.strip()


def _require_url(value: Any, field: str) -> str:
    url = _require_text(value, field)
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme in {"https", "http"} and bool(parsed.netloc)
    except ValueError:
        valid = False
    if not valid:
        raise CalendarDataError(f"{field} must be a valid HTTP(S) URL.")
    return url


def _parse_date(value: Any, field: str) -> date:
    valid_format = (
        isinstance(value, str)
        and len(value) == 10
        and value[4] == "-"
        and value[7] == "-"
        and value[:4].isascii()
        and value[:4].isdigit()
        and value[5:7].isascii()
        and value[5:7].isdigit()
        and value[8:10].isascii()
        and value[8:10].isdigit()
    )
    if not valid_format:
        raise CalendarDataError(f"{field} must be an ISO date.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CalendarDataError(f"{field} must be a valid ISO date.") from exc



def parse_calendar_date(
    value: Any,
    *,
    calendar: str = "gregorian",
    expected_jalali_year: int | None = None,
) -> date:
    """Parse a strict Gregorian or Jalali ISO date and return a Gregorian date."""
    if not isinstance(calendar, str) or calendar not in {"gregorian", "jalali"}:
        raise CalendarDataError("calendar must be 'gregorian' or 'jalali'.")

    if expected_jalali_year is not None and (
        isinstance(expected_jalali_year, bool)
        or not isinstance(expected_jalali_year, int)
        or expected_jalali_year < 1200
    ):
        raise CalendarDataError("Invalid expected_jalali_year.")

    if calendar == "gregorian":
        result = _parse_date(value, "date")
    else:
        valid_format = (
            isinstance(value, str)
            and len(value) == 10
            and value[4] == "-"
            and value[7] == "-"
            and value[:4].isascii()
            and value[:4].isdigit()
            and value[5:7].isascii()
            and value[5:7].isdigit()
            and value[8:10].isascii()
            and value[8:10].isdigit()
        )
        if not valid_format:
            raise CalendarDataError("date must be a Jalali ISO date.")

        try:
            jalali = JalaliDate(
                int(value[:4]), int(value[5:7]), int(value[8:10])
            )
            result = jalali.to_gregorian()
        except (ValueError, OverflowError) as exc:
            raise CalendarDataError("date must be a valid Jalali date.") from exc

    if (
        expected_jalali_year is not None
        and jalali_year_for_date(result) != expected_jalali_year
    ):
        raise CalendarDataError("date does not belong to expected_jalali_year.")

    return result

def _parse_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or "T" not in value:
        raise CalendarDataError(f"{field} must be an ISO datetime.")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        result = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CalendarDataError(f"{field} must be an ISO datetime.") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise CalendarDataError(f"{field} must include a timezone.")
    return result


@dataclass(frozen=True)
class CalendarHoliday:
    day: date
    name: str
    source: str
    source_url: str

    def __post_init__(self):
        if isinstance(self.day, datetime) or not isinstance(self.day, date):
            raise CalendarDataError("Holiday day must be a date, not a datetime.")
        _require_text(self.name, "holiday.name")
        _require_text(self.source, "holiday.source")
        _require_url(self.source_url, "holiday.source_url")


@dataclass(frozen=True)
class MarketScope:
    """The exact market or operation affected by an event."""

    level: str
    market: str | None = None
    symbol: str | None = None
    operation: str | None = None

    LEVELS = frozenset({
        "all_market",
        "market",
        "symbol",
        "fund_operation",
    })

    def __post_init__(self):
        if not isinstance(self.level, str) or self.level not in self.LEVELS:
            raise CalendarDataError("Unsupported event scope level.")

        for field in ("market", "symbol", "operation"):
            value = getattr(self, field)
            if value is not None:
                _require_text(value, f"scope.{field}")

        if self.level == "all_market":
            if any(value is not None for value in (
                self.market, self.symbol, self.operation
            )):
                raise CalendarDataError("all_market scope cannot contain narrower fields.")

        elif self.level == "market":
            if not self.market:
                raise CalendarDataError("Market scope requires a market.")
            if self.symbol is not None or self.operation is not None:
                raise CalendarDataError("Market scope cannot contain symbol or operation.")

        elif self.level == "symbol":
            if not self.symbol:
                raise CalendarDataError("Symbol scope requires a symbol.")
            if self.operation is not None:
                raise CalendarDataError("Symbol scope cannot contain operation.")

        elif self.level == "fund_operation":
            if not self.operation:
                raise CalendarDataError("Fund operation scope requires an operation.")
            if self.symbol is not None:
                raise CalendarDataError("Fund operation scope cannot contain symbol.")

    def matches(
        self,
        *,
        market: str | None,
        symbol: str | None,
        operation: str | None,
    ) -> bool:
        if self.level == "all_market":
            return True
        if self.level == "market":
            return market == self.market
        if self.level == "symbol":
            return symbol == self.symbol and (
                self.market is None or market == self.market
            )
        if self.level == "fund_operation":
            return (
                operation == self.operation
                and (self.market is None or market == self.market)
            )
        return False


@dataclass(frozen=True)
class CalendarEvent:
    event_id: str
    title: str
    issuer: str
    source_url: str
    published_at: datetime
    effective_from: date
    effective_to: date
    scope: MarketScope
    status: str
    expires_at: datetime | None = None

    def __post_init__(self):
        for field in ("event_id", "title", "issuer"):
            _require_text(getattr(self, field), f"event.{field}")
        _require_url(self.source_url, "event.source_url")

        if self.status not in {"confirmed", "unverified"}:
            raise CalendarDataError("Event status must be confirmed or unverified.")

        if not isinstance(self.published_at, datetime):
            raise CalendarDataError("published_at must be a datetime.")
        if self.published_at.tzinfo is None or self.published_at.utcoffset() is None:
            raise CalendarDataError("published_at must include a timezone.")

        if isinstance(self.effective_from, datetime) or not isinstance(self.effective_from, date):
            raise CalendarDataError("effective_from must be a date.")
        if isinstance(self.effective_to, datetime) or not isinstance(self.effective_to, date):
            raise CalendarDataError("effective_to must be a date.")

        if self.expires_at is not None:
            if not isinstance(self.expires_at, datetime):
                raise CalendarDataError("expires_at must be a datetime.")
            if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
                raise CalendarDataError("expires_at must include a timezone.")

        if not isinstance(self.scope, MarketScope):
            raise CalendarDataError("scope must be a MarketScope.")

        if self.effective_to < self.effective_from:
            raise CalendarDataError("Event effective date range is invalid.")


@dataclass(frozen=True)
class CalendarDayStatus:
    day: date
    status: str
    is_official_holiday: bool
    is_closed: bool
    holidays: tuple[CalendarHoliday, ...]
    closure_events: tuple[CalendarEvent, ...]
    warnings: tuple[CalendarEvent, ...]


class MarketCalendar:
    """Official holidays and explicitly reviewed, scoped closure events."""

    def __init__(
        self,
        holidays: Iterable[CalendarHoliday] = (),
        events: Iterable[CalendarEvent] = (),
        *,
        calendar_year: int | None = None,
        jalali_year: int | None = None,
        source: str | None = None,
        source_url: str | None = None,
        updated_at: datetime | None = None,
    ):
        self.holidays = tuple(holidays)
        self.events = tuple(events)
        self.calendar_year = calendar_year
        self.jalali_year = jalali_year
        self.source = source
        self.source_url = source_url
        self.updated_at = updated_at

        if calendar_year is not None and (
            isinstance(calendar_year, bool)
            or not isinstance(calendar_year, int)
            or calendar_year < 1900
        ):
            raise CalendarDataError("Invalid calendar_year.")

        if jalali_year is not None and (
            isinstance(jalali_year, bool)
            or not isinstance(jalali_year, int)
            or jalali_year < 1200
        ):
            raise CalendarDataError("Invalid jalali_year.")

        if source is not None:
            _require_text(source, "source")
        if source_url is not None:
            _require_url(source_url, "source_url")
        if updated_at is not None:
            if not isinstance(updated_at, datetime):
                raise CalendarDataError("updated_at must be a datetime.")
            if updated_at.tzinfo is None or updated_at.utcoffset() is None:
                raise CalendarDataError("updated_at must include a timezone.")

        if any(not isinstance(item, CalendarHoliday) for item in self.holidays):
            raise CalendarDataError("holidays must contain CalendarHoliday items.")
        if any(not isinstance(item, CalendarEvent) for item in self.events):
            raise CalendarDataError("events must contain CalendarEvent items.")

        if len({item.day for item in self.holidays}) != len(self.holidays):
            raise CalendarDataError("Duplicate holiday dates are not allowed.")

        if len({item.event_id for item in self.events}) != len(self.events):
            raise CalendarDataError("Duplicate event IDs are not allowed.")

    @classmethod
    def from_json(
        cls,
        path: str | Path,
        *,
        events: Iterable[CalendarEvent] = (),
    ) -> "MarketCalendar":
        """Load a strictly validated, versioned annual holiday file."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
            raise CalendarDataError("Unable to read calendar JSON.") from exc

        if not isinstance(data, dict):
            raise CalendarDataError("Calendar JSON must be an object.")

        schema_version = data.get("schema_version")
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != 1
        ):
            raise CalendarDataError("Unsupported calendar schema.")

        calendar_year = data.get("calendar_year")
        jalali_year = data.get("jalali_year")
        for value, field, minimum in (
            (calendar_year, "calendar_year", 1900),
            (jalali_year, "jalali_year", 1200),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < minimum
            ):
                raise CalendarDataError(f"Invalid {field}.")

        try:
            expected_calendar_year = JalaliDate(
                jalali_year, 1, 1
            ).to_gregorian().year
        except (ValueError, OverflowError) as exc:
            raise CalendarDataError("Invalid jalali_year.") from exc

        if calendar_year != expected_calendar_year:
            raise CalendarDataError(
                "calendar_year must be the Gregorian start year of jalali_year."
            )

        source = _require_text(data.get("source"), "source")
        source_url = _require_url(data.get("source_url"), "source_url")
        updated_at = _parse_datetime(data.get("updated_at"), "updated_at")

        raw_holidays = data.get("holidays")
        if not isinstance(raw_holidays, list):
            raise CalendarDataError("holidays must be a list.")

        holidays = []
        for index, item in enumerate(raw_holidays):
            if not isinstance(item, dict):
                raise CalendarDataError(f"holidays[{index}] must be an object.")

            holiday_day = _parse_date(
                item.get("date"), f"holidays[{index}].date"
            )
            if jalali_year_for_date(holiday_day) != jalali_year:
                raise CalendarDataError(
                    f"holidays[{index}].date does not belong to jalali_year."
                )

            holidays.append(
                CalendarHoliday(
                    day=holiday_day,
                    name=_require_text(
                        item.get("name"), f"holidays[{index}].name"
                    ),
                    source=_require_text(
                        item.get("source"), f"holidays[{index}].source"
                    ),
                    source_url=_require_url(
                        item.get("source_url"),
                        f"holidays[{index}].source_url",
                    ),
                )
            )

        return cls(
            holidays=holidays,
            events=events,
            calendar_year=calendar_year,
            jalali_year=jalali_year,
            source=source,
            source_url=source_url,
            updated_at=updated_at,
        )

    def get_status(
        self,
        day: date,
        *,
        market: str | None = None,
        symbol: str | None = None,
        operation: str | None = None,
        now: datetime | None = None,
    ) -> CalendarDayStatus:
        if isinstance(day, datetime) or not isinstance(day, date):
            raise CalendarDataError("day must be a date, not a datetime.")

        current = datetime.now(timezone.utc) if now is None else now
        if not isinstance(current, datetime):
            raise CalendarDataError("now must be a datetime.")
        if current.tzinfo is None or current.utcoffset() is None:
            raise CalendarDataError("now must include a timezone.")

        holidays = tuple(item for item in self.holidays if item.day == day)
        matching_events = []

        for event in self.events:
            if not event.effective_from <= day <= event.effective_to:
                continue
            if event.expires_at is not None and current > event.expires_at:
                continue
            if not event.scope.matches(
                market=market,
                symbol=symbol,
                operation=operation,
            ):
                continue
            matching_events.append(event)

        closures = tuple(
            event for event in matching_events if event.status == "confirmed"
        )
        warnings = tuple(
            event for event in matching_events if event.status == "unverified"
        )

        is_holiday = bool(holidays)
        is_closed = is_holiday or bool(closures)

        if is_holiday:
            status = "official_holiday"
        elif closures:
            status = "emergency_closure"
        elif warnings:
            status = "open_with_unverified_notice"
        else:
            status = "open"

        return CalendarDayStatus(
            day=day,
            status=status,
            is_official_holiday=is_holiday,
            is_closed=is_closed,
            holidays=holidays,
            closure_events=closures,
            warnings=warnings,
        )

def load_market_events(path: str | Path) -> tuple[CalendarEvent, ...]:
    """Load strictly validated, independently maintained market events."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
        raise CalendarDataError("Unable to read market events JSON.") from exc

    if not isinstance(data, dict):
        raise CalendarDataError("Market events JSON must be an object.")

    schema_version = data.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != 1
    ):
        raise CalendarDataError("Unsupported market events schema.")

    _parse_datetime(data.get("updated_at"), "events.updated_at")

    raw_events = data.get("events")
    if not isinstance(raw_events, list):
        raise CalendarDataError("events must be a list.")

    allowed_event_fields = {
        "event_id", "title", "issuer", "source_url", "published_at",
        "effective_from", "effective_to", "scope", "status", "expires_at",
    }
    allowed_scope_fields = {"level", "market", "symbol", "operation"}

    events = []
    for index, item in enumerate(raw_events):
        prefix = f"events[{index}]"
        if not isinstance(item, dict):
            raise CalendarDataError(f"{prefix} must be an object.")

        unknown_fields = set(item) - allowed_event_fields
        if unknown_fields:
            raise CalendarDataError(
                f"{prefix} contains unsupported fields: {sorted(unknown_fields)}"
            )

        scope_data = item.get("scope")
        if not isinstance(scope_data, dict):
            raise CalendarDataError(f"{prefix}.scope must be an object.")

        unknown_scope_fields = set(scope_data) - allowed_scope_fields
        if unknown_scope_fields:
            raise CalendarDataError(
                f"{prefix}.scope contains unsupported fields: "
                f"{sorted(unknown_scope_fields)}"
            )

        scope = MarketScope(
            level=_require_text(scope_data.get("level"), f"{prefix}.scope.level"),
            market=scope_data.get("market"),
            symbol=scope_data.get("symbol"),
            operation=scope_data.get("operation"),
        )

        expires_value = item.get("expires_at")
        expires_at = (
            None
            if expires_value is None
            else _parse_datetime(expires_value, f"{prefix}.expires_at")
        )

        events.append(
            CalendarEvent(
                event_id=_require_text(item.get("event_id"), f"{prefix}.event_id"),
                title=_require_text(item.get("title"), f"{prefix}.title"),
                issuer=_require_text(item.get("issuer"), f"{prefix}.issuer"),
                source_url=_require_url(
                    item.get("source_url"), f"{prefix}.source_url"
                ),
                published_at=_parse_datetime(
                    item.get("published_at"), f"{prefix}.published_at"
                ),
                effective_from=_parse_date(
                    item.get("effective_from"), f"{prefix}.effective_from"
                ),
                effective_to=_parse_date(
                    item.get("effective_to"), f"{prefix}.effective_to"
                ),
                scope=scope,
                status=_require_text(item.get("status"), f"{prefix}.status"),
                expires_at=expires_at,
            )
        )

    # Reuse the calendar's duplicate-ID validation.
    MarketCalendar(events=events)
    return tuple(events)

