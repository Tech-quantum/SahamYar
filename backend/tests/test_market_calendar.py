import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app.market_calendar import (
    CalendarDataError,
    CalendarEvent,
    CalendarHoliday,
    MarketCalendar,
    MarketScope,
    current_jalali_year,
    jalali_year_for_date,
    load_market_events,
    parse_calendar_date,
)


SOURCE_URL = "https://www.example.com/official-notice"
NOW = datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc)


def make_event(
    *,
    event_id="event-1",
    scope=None,
    status="confirmed",
    effective_from=date(2026, 11, 24),
    effective_to=date(2026, 11, 24),
    expires_at=None,
):
    return CalendarEvent(
        event_id=event_id,
        title="Market closure notice",
        issuer="Official authority",
        source_url=SOURCE_URL,
        published_at=NOW - timedelta(hours=1),
        effective_from=effective_from,
        effective_to=effective_to,
        scope=scope or MarketScope(level="all_market"),
        status=status,
        expires_at=expires_at,
    )


def test_official_holiday_closes_day_and_preserves_provenance():
    holiday = CalendarHoliday(
        day=date(2026, 11, 24),
        name="Official holiday",
        source="Official calendar",
        source_url=SOURCE_URL,
    )
    calendar = MarketCalendar(holidays=[holiday])

    result = calendar.get_status(date(2026, 11, 24), now=NOW)

    assert result.is_closed is True
    assert result.is_official_holiday is True
    assert result.status == "official_holiday"
    assert result.holidays[0].source == "Official calendar"
    assert result.holidays[0].source_url == SOURCE_URL


def test_confirmed_all_market_event_closes_market():
    calendar = MarketCalendar(events=[make_event()])

    result = calendar.get_status(date(2026, 11, 24), now=NOW)

    assert result.is_closed is True
    assert result.status == "emergency_closure"
    assert len(result.closure_events) == 1


def test_market_specific_event_only_matches_that_market():
    event = make_event(
        scope=MarketScope(level="market", market="stock_exchange")
    )
    calendar = MarketCalendar(events=[event])

    matching = calendar.get_status(
        date(2026, 11, 24), market="stock_exchange", now=NOW
    )
    unrelated = calendar.get_status(
        date(2026, 11, 24), market="commodity_exchange", now=NOW
    )

    assert matching.is_closed is True
    assert unrelated.is_closed is False
    assert unrelated.status == "open"


def test_fund_operation_event_only_matches_its_operation():
    event = make_event(
        scope=MarketScope(
            level="fund_operation",
            market="mutual_funds",
            operation="subscription_redemption",
        )
    )
    calendar = MarketCalendar(events=[event])

    matching = calendar.get_status(
        date(2026, 11, 24),
        market="mutual_funds",
        operation="subscription_redemption",
        now=NOW,
    )
    unrelated = calendar.get_status(
        date(2026, 11, 24),
        market="mutual_funds",
        operation="trading",
        now=NOW,
    )

    assert matching.is_closed is True
    assert unrelated.is_closed is False


def test_unverified_event_is_warning_not_closure():
    event = make_event(status="unverified")
    calendar = MarketCalendar(events=[event])

    result = calendar.get_status(date(2026, 11, 24), now=NOW)

    assert result.is_closed is False
    assert result.status == "open_with_unverified_notice"
    assert len(result.warnings) == 1
    assert result.closure_events == ()


def test_expired_event_is_ignored():
    event = make_event(expires_at=NOW - timedelta(minutes=1))
    calendar = MarketCalendar(events=[event])

    result = calendar.get_status(date(2026, 11, 24), now=NOW)

    assert result.is_closed is False
    assert result.status == "open"


def test_event_outside_effective_date_is_ignored():
    event = make_event(
        effective_from=date(2026, 11, 25),
        effective_to=date(2026, 11, 26),
    )
    calendar = MarketCalendar(events=[event])

    result = calendar.get_status(date(2026, 11, 24), now=NOW)

    assert result.is_closed is False


def test_from_json_loads_holidays_and_metadata(tmp_path):
    payload = {
        "schema_version": 1,
        "calendar_year": 2026,
        "jalali_year": 1405,
        "source": "Official calendar",
        "source_url": SOURCE_URL,
        "updated_at": "2026-01-01T10:00:00+03:30",
        "holidays": [
            {
                "date": "2026-11-24",
                "name": "Official holiday",
                "source": "Official calendar",
                "source_url": SOURCE_URL,
            }
        ],
    }
    path = tmp_path / "calendar.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    calendar = MarketCalendar.from_json(path)

    assert calendar.calendar_year == 2026
    assert calendar.jalali_year == 1405
    assert calendar.holidays[0].day == date(2026, 11, 24)


@pytest.mark.parametrize(
    "payload",
    [
        "{invalid json",
        '{"schema_version": 2, "holidays": []}',
        '{"schema_version": 1, "holidays": "not-a-list"}',
        (
            '{"schema_version": 1, "holidays": [{"date": "2026-11-24",'
            ' "name": "Holiday", "source": "Official"}]}'
        ),
    ],
)
def test_invalid_json_or_missing_provenance_is_rejected(tmp_path, payload):
    path = tmp_path / "invalid.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(CalendarDataError):
        MarketCalendar.from_json(path)



def make_valid_calendar_payload():
    return {
        "schema_version": 1,
        "calendar_year": 2026,
        "jalali_year": 1405,
        "source": "Official calendar",
        "source_url": SOURCE_URL,
        "updated_at": "2026-01-01T10:00:00+03:30",
        "holidays": [
            {
                "date": "2026-11-24",
                "name": "Official holiday",
                "source": "Official calendar",
                "source_url": SOURCE_URL,
            }
        ],
    }


@pytest.mark.parametrize(
    "invalid_date",
    [
        "2026-13-35",
        "2026-02-30",
        "20261124",
        "2026-W48-2",
        "۱۴۰۵-۰۹-۰۳",
        "1405/13/35",
        "2025-03-20",
    ],
)
def test_from_json_rejects_invalid_calendar_dates(tmp_path, invalid_date):
    payload = make_valid_calendar_payload()
    payload["holidays"][0]["date"] = invalid_date
    path = tmp_path / "invalid-date.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CalendarDataError):
        MarketCalendar.from_json(path)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("schema_version", True),
        ("calendar_year", True),
        ("calendar_year", "2026"),
        ("jalali_year", True),
        ("jalali_year", "1405"),
        ("calendar_year", 2025),
        ("source", ""),
        ("source_url", "not-a-url"),
        ("updated_at", "2026-01-01T10:00:00"),
    ],
)
def test_from_json_rejects_invalid_metadata(tmp_path, field, invalid_value):
    payload = make_valid_calendar_payload()
    payload[field] = invalid_value
    path = tmp_path / "invalid-metadata.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CalendarDataError):
        MarketCalendar.from_json(path)

def test_duplicate_holiday_dates_are_rejected():
    holiday = CalendarHoliday(
        day=date(2026, 11, 24),
        name="Holiday",
        source="Official calendar",
        source_url=SOURCE_URL,
    )

    with pytest.raises(CalendarDataError, match="Duplicate holiday"):
        MarketCalendar(holidays=[holiday, holiday])


def test_duplicate_event_ids_are_rejected():
    first = make_event(event_id="duplicate")
    second = make_event(event_id="duplicate")

    with pytest.raises(CalendarDataError, match="Duplicate event"):
        MarketCalendar(events=[first, second])


@pytest.mark.parametrize(
    "scope",
    [
        {"level": "unknown"},
        {"level": "market"},
        {"level": "symbol"},
        {"level": "fund_operation"},
    ],
)
def test_scope_required_fields_are_validated(scope):
    with pytest.raises(CalendarDataError):
        MarketScope(**scope)


def test_naive_timestamps_are_rejected():
    with pytest.raises(CalendarDataError, match="timezone"):
        make_event_with_naive_timestamp()


def make_event_with_naive_timestamp():
    return CalendarEvent(
        event_id="naive",
        title="Notice",
        issuer="Authority",
        source_url=SOURCE_URL,
        published_at=datetime(2026, 11, 24, 9, 0),
        effective_from=date(2026, 11, 24),
        effective_to=date(2026, 11, 24),
        scope=MarketScope(level="all_market"),
        status="confirmed",
    )


def test_naive_now_is_rejected():
    calendar = MarketCalendar()

    with pytest.raises(CalendarDataError, match="timezone"):
        calendar.get_status(
            date(2026, 11, 24),
            now=datetime(2026, 11, 24, 10, 0),
        )


@pytest.mark.parametrize(
    ("gregorian", "expected_year"),
    [
        (date(2026, 3, 20), 1404),
        (date(2026, 3, 21), 1405),
        (date(2027, 3, 20), 1405),
        (date(2027, 3, 21), 1406),
    ],
)
def test_jalali_year_boundary_dates(gregorian, expected_year):
    assert jalali_year_for_date(gregorian) == expected_year


def test_jalali_year_rejects_datetime_input():
    with pytest.raises(CalendarDataError, match="not a datetime"):
        jalali_year_for_date(datetime(2026, 3, 21, 0, 0))


def test_current_jalali_year_uses_tehran_timezone_at_new_year():
    before_new_year_utc = datetime(2026, 3, 20, 20, 29, tzinfo=timezone.utc)
    at_new_year_utc = datetime(2026, 3, 20, 20, 30, tzinfo=timezone.utc)

    assert current_jalali_year(before_new_year_utc) == 1404
    assert current_jalali_year(at_new_year_utc) == 1405


def test_current_jalali_year_rejects_naive_datetime():
    with pytest.raises(CalendarDataError, match="timezone"):
        current_jalali_year(datetime(2026, 3, 21, 0, 0))


def test_current_jalali_year_rejects_non_datetime():
    with pytest.raises(CalendarDataError, match="datetime"):
        current_jalali_year(date(2026, 3, 21))


# Strict model validation regression tests
from dataclasses import replace


def test_holiday_rejects_datetime():
    with pytest.raises(CalendarDataError, match="not a datetime"):
        CalendarHoliday(
            day=datetime(2026, 11, 24, 10, 0),
            name="Holiday",
            source="Official",
            source_url=SOURCE_URL,
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"published_at": "2026-11-24T10:00:00+00:00"},
        {"published_at": None},
        {"published_at": datetime(2026, 11, 24, 10, 0)},
        {"expires_at": "2026-11-25T10:00:00+00:00"},
        {"expires_at": datetime(2026, 11, 25, 10, 0)},
        {"effective_from": datetime(2026, 11, 24, 10, 0)},
        {"effective_to": datetime(2026, 11, 24, 10, 0)},
        {"scope": "all_market"},
    ],
)
def test_event_rejects_invalid_field_types(changes):
    with pytest.raises(CalendarDataError):
        replace(make_event(), **changes)


@pytest.mark.parametrize(
    "scope_kwargs",
    [
        {"level": "all_market", "market": "stock_exchange"},
        {"level": "all_market", "symbol": "FOLD"},
        {"level": "all_market", "operation": "trading"},
        {"level": "market", "market": "stock_exchange", "symbol": "FOLD"},
        {"level": "market", "market": "stock_exchange", "operation": "trading"},
        {"level": "symbol", "symbol": "FOLD", "operation": "trading"},
        {"level": "fund_operation", "operation": "subscription", "symbol": "FOLD"},
    ],
)
def test_scope_rejects_incompatible_extra_fields(scope_kwargs):
    with pytest.raises(CalendarDataError):
        MarketScope(**scope_kwargs)


def test_symbol_and_fund_operation_scopes_allow_optional_market():
    symbol_scope = MarketScope(level="symbol", symbol="FOLD")
    fund_scope = MarketScope(level="fund_operation", operation="subscription")

    assert symbol_scope.matches(market=None, symbol="FOLD", operation=None)
    assert fund_scope.matches(market=None, symbol=None, operation="subscription")


@pytest.mark.parametrize(
    "updated_at",
    [
        "2026-11-24T10:00:00+00:00",
        datetime(2026, 11, 24, 10, 0),
    ],
)
def test_market_calendar_rejects_invalid_updated_at(updated_at):
    with pytest.raises(CalendarDataError):
        MarketCalendar(updated_at=updated_at)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"holidays": ["not-a-holiday"]},
        {"events": ["not-an-event"]},
    ],
)
def test_market_calendar_rejects_invalid_collection_items(kwargs):
    with pytest.raises(CalendarDataError):
        MarketCalendar(**kwargs)


def test_get_status_rejects_datetime_as_day():
    with pytest.raises(CalendarDataError, match="not a datetime"):
        MarketCalendar().get_status(datetime(2026, 11, 24, 10, 0))


@pytest.mark.parametrize(
    "invalid_now",
    [
        "2026-11-24T10:00:00+00:00",
        date(2026, 11, 24),
    ],
)
def test_get_status_rejects_non_datetime_now(invalid_now):
    with pytest.raises(CalendarDataError, match="datetime"):
        MarketCalendar().get_status(date(2026, 11, 24), now=invalid_now)


@pytest.mark.parametrize(
    ("value", "calendar", "expected"),
    [
        ("2026-11-24", "gregorian", date(2026, 11, 24)),
        ("1405-09-03", "jalali", date(2026, 11, 24)),
        ("1405-01-01", "jalali", date(2026, 3, 21)),
    ],
)
def test_parse_calendar_date_valid_inputs(value, calendar, expected):
    assert parse_calendar_date(value, calendar=calendar) == expected


@pytest.mark.parametrize(
    ("value", "calendar"),
    [
        ("2026-13-35", "gregorian"),
        ("2026-02-30", "gregorian"),
        ("2026/11/24", "gregorian"),
        ("1405-13-35", "jalali"),
        ("1405-12-30", "jalali"),
        ("1405/09/03", "jalali"),
        ("۱۴۰۵-۰۹-۰۳", "jalali"),
        ("14050903", "jalali"),
        (None, "jalali"),
    ],
)
def test_parse_calendar_date_rejects_invalid_inputs(value, calendar):
    with pytest.raises(CalendarDataError):
        parse_calendar_date(value, calendar=calendar)


def test_parse_calendar_date_rejects_unknown_calendar():
    with pytest.raises(CalendarDataError, match="calendar"):
        parse_calendar_date("2026-11-24", calendar="persian")


@pytest.mark.parametrize("invalid_calendar", [None, [], {}, 123, True])
def test_parse_calendar_date_rejects_non_string_calendar(invalid_calendar):
    with pytest.raises(CalendarDataError, match="calendar"):
        parse_calendar_date("2026-11-24", calendar=invalid_calendar)


@pytest.mark.parametrize("expected_year", [True, "1405", 1199])
def test_parse_calendar_date_rejects_invalid_expected_year(expected_year):
    with pytest.raises(CalendarDataError, match="expected_jalali_year"):
        parse_calendar_date(
            "1405-09-03",
            calendar="jalali",
            expected_jalali_year=expected_year,
        )


@pytest.mark.parametrize(
    ("value", "calendar", "expected_year"),
    [
        ("1405-09-03", "jalali", 1404),
        ("2026-11-24", "gregorian", 1404),
    ],
)
def test_parse_calendar_date_rejects_wrong_jalali_year(
    value, calendar, expected_year
):
    with pytest.raises(CalendarDataError, match="expected_jalali_year"):
        parse_calendar_date(
            value,
            calendar=calendar,
            expected_jalali_year=expected_year,
        )

def make_valid_market_events_payload():
    return {
        "schema_version": 1,
        "updated_at": "2026-11-24T20:00:00+03:30",
        "events": [
            {
                "event_id": "closure-001",
                "title": "Symbol-specific trading halt",
                "issuer": "Official authority",
                "source_url": SOURCE_URL,
                "published_at": "2026-11-24T19:00:00+03:30",
                "effective_from": "2026-11-25",
                "effective_to": "2026-11-25",
                "scope": {
                    "level": "symbol",
                    "market": "بورس",
                    "symbol": "فولاد",
                    "operation": None,
                },
                "status": "confirmed",
                "expires_at": None,
            }
        ],
    }


def test_load_market_events_accepts_empty_event_list(tmp_path):
    path = tmp_path / "market_events.json"
    path.write_text(
        json.dumps({
            "schema_version": 1,
            "updated_at": "2026-11-24T20:00:00+03:30",
            "events": [],
        }),
        encoding="utf-8",
    )

    assert load_market_events(path) == ()


def test_load_market_events_parses_event_and_scope(tmp_path):
    path = tmp_path / "market_events.json"
    path.write_text(
        json.dumps(make_valid_market_events_payload()),
        encoding="utf-8",
    )

    events = load_market_events(path)

    assert len(events) == 1
    event = events[0]
    assert event.event_id == "closure-001"
    assert event.effective_from == date(2026, 11, 25)
    assert event.effective_to == date(2026, 11, 25)
    assert event.published_at.utcoffset() == timedelta(hours=3, minutes=30)
    assert event.scope.level == "symbol"
    assert event.scope.market == "بورس"
    assert event.scope.symbol == "فولاد"
    assert event.status == "confirmed"


@pytest.mark.parametrize(
    "invalid_version",
    [True, 1.0, "1", 2, None],
)
def test_load_market_events_rejects_invalid_schema_version(
    tmp_path, invalid_version
):
    payload = make_valid_market_events_payload()
    payload["schema_version"] = invalid_version
    path = tmp_path / "market_events.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CalendarDataError, match="schema"):
        load_market_events(path)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("title", ""),
        ("source_url", "not-a-url"),
        ("published_at", "2026-11-24T19:00:00"),
        ("effective_from", "2026-02-30"),
        ("status", "pending"),
        ("expires_at", "2026-11-25T10:00:00"),
    ],
)
def test_load_market_events_rejects_invalid_event_fields(
    tmp_path, field, invalid_value
):
    payload = make_valid_market_events_payload()
    payload["events"][0][field] = invalid_value
    path = tmp_path / "market_events.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CalendarDataError):
        load_market_events(path)


@pytest.mark.parametrize(
    "invalid_scope",
    [
        None,
        "all_market",
        {"level": "unknown"},
        {"level": "symbol"},
        {"level": "all_market", "symbol": "فولاد"},
        {"level": "all_market", "unexpected": "value"},
    ],
)
def test_load_market_events_rejects_invalid_scope(tmp_path, invalid_scope):
    payload = make_valid_market_events_payload()
    payload["events"][0]["scope"] = invalid_scope
    path = tmp_path / "market_events.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CalendarDataError):
        load_market_events(path)


def test_load_market_events_rejects_duplicate_event_ids(tmp_path):
    payload = make_valid_market_events_payload()
    payload["events"].append(dict(payload["events"][0]))
    path = tmp_path / "market_events.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CalendarDataError, match="Duplicate event IDs"):
        load_market_events(path)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"schema_version": 1, "updated_at": "2026-11-24T20:00:00+03:30"},
        {
            "schema_version": 1,
            "updated_at": "2026-11-24T20:00:00",
            "events": [],
        },
        {
            "schema_version": 1,
            "updated_at": "2026-11-24T20:00:00+03:30",
            "events": {},
        },
    ],
)
def test_load_market_events_rejects_invalid_root_data(tmp_path, payload):
    path = tmp_path / "market_events.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CalendarDataError):
        load_market_events(path)


def test_load_market_events_rejects_invalid_json_and_missing_file(tmp_path):
    path = tmp_path / "market_events.json"
    path.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(CalendarDataError):
        load_market_events(path)

    with pytest.raises(CalendarDataError):
        load_market_events(tmp_path / "missing.json")



def test_symbol_scope_with_market_only_matches_that_market():
    event = make_event(
        scope=MarketScope(
            level="symbol",
            market="stock_exchange",
            symbol="فولاد",
        )
    )
    calendar = MarketCalendar(events=[event])

    matching = calendar.get_status(
        date(2026, 11, 24),
        market="stock_exchange",
        symbol="فولاد",
        now=NOW,
    )
    wrong_market = calendar.get_status(
        date(2026, 11, 24),
        market="commodity_exchange",
        symbol="فولاد",
        now=NOW,
    )
    wrong_symbol = calendar.get_status(
        date(2026, 11, 24),
        market="stock_exchange",
        symbol="فملی",
        now=NOW,
    )

    assert matching.is_closed is True
    assert wrong_market.is_closed is False
    assert wrong_symbol.is_closed is False
