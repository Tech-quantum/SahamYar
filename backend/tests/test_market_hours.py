from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.market_hours import MarketHours


TEHRAN = ZoneInfo("Asia/Tehran")


def at(hour, minute, day=17):
    return datetime(2026, 11, day, hour, minute, tzinfo=TEHRAN)


def test_pre_open_schedule():
    status = MarketHours().get_status(at(8, 50))
    assert status.phase == "pre_open"
    assert status.interval_seconds == 60
    assert status.is_trading_day is True


def test_continuous_market_schedule():
    status = MarketHours().get_status(at(10, 15))
    assert status.phase == "continuous"
    assert status.interval_seconds == 20


def test_post_market_schedule():
    status = MarketHours().get_status(at(12, 45))
    assert status.phase == "post_market"
    assert status.interval_seconds == 300


def test_before_pre_open_is_closed():
    status = MarketHours().get_status(at(8, 44))
    assert status.phase == "closed"
    assert status.interval_seconds == 3600


def test_after_post_market_is_closed():
    status = MarketHours().get_status(at(13, 0))
    assert status.phase == "closed"


def test_thursday_is_not_a_trading_day():
    # 19 November 2026 is Thursday.
    status = MarketHours().get_status(at(10, 0, day=19))
    assert status.phase == "closed"
    assert status.is_trading_day is False


def test_friday_is_not_a_trading_day():
    # 20 November 2026 is Friday.
    status = MarketHours().get_status(at(10, 0, day=20))
    assert status.phase == "closed"
    assert status.is_trading_day is False


def test_configured_holiday_is_closed():
    holiday = date(2026, 11, 17)
    status = MarketHours(holidays={holiday}).get_status(at(10, 0))
    assert status.phase == "closed"
    assert status.is_trading_day is False


def test_utc_input_is_converted_to_tehran_time():
    utc = datetime.fromisoformat("2026-11-17T05:30:00+00:00")
    status = MarketHours().get_status(utc)
    assert status.phase == "continuous"
    assert status.local_time.startswith("2026-11-17T09:00:00+03:30")


def test_official_calendar_holiday_closes_market():
    from app.market_calendar import CalendarHoliday, MarketCalendar

    holiday = CalendarHoliday(
        day=date(2026, 11, 17),
        name="Official holiday",
        source="Official calendar",
        source_url="https://example.com/calendar",
    )
    calendar = MarketCalendar(holidays=[holiday], jalali_year=1405)

    status = MarketHours(calendar=calendar, require_calendar=True).get_status(
        at(10, 0)
    )

    assert status.phase == "closed"
    assert status.calendar_status == "official_holiday"


def test_unverified_calendar_event_does_not_close_market():
    from datetime import timedelta, timezone
    from app.market_calendar import CalendarEvent, MarketCalendar, MarketScope

    now = datetime(2026, 11, 17, 10, 0, tzinfo=TEHRAN)
    event = CalendarEvent(
        event_id="unverified-1",
        title="Unverified closure notice",
        issuer="Test issuer",
        source_url="https://example.com/notice",
        published_at=now - timedelta(hours=1),
        effective_from=now.date(),
        effective_to=now.date(),
        scope=MarketScope(level="all_market"),
        status="unverified",
    )
    calendar = MarketCalendar(events=[event], jalali_year=1405)

    status = MarketHours(calendar=calendar, require_calendar=True).get_status(now)

    assert status.phase == "continuous"
    assert status.calendar_status == "open_with_unverified_notice"
    assert status.calendar_warnings == ("Unverified closure notice",)


def test_missing_required_calendar_fails_closed():
    status = MarketHours(require_calendar=True).get_status(at(10, 0))

    assert status.phase == "closed"
    assert status.is_trading_day is False
    assert status.calendar_status == "needs_update"


def test_previous_jalali_year_calendar_fails_closed():
    from app.market_calendar import MarketCalendar

    calendar = MarketCalendar(jalali_year=1404)
    status = MarketHours(calendar=calendar, require_calendar=True).get_status(
        at(10, 0)
    )

    assert status.phase == "closed"
    assert status.calendar_status == "needs_update"


def test_calendar_error_fails_closed():
    status = MarketHours(
        require_calendar=True,
        calendar_error="Invalid calendar file",
    ).get_status(at(10, 0))

    assert status.phase == "closed"
    assert status.calendar_status == "invalid"
