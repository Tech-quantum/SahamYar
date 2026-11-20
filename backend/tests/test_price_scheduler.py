from types import SimpleNamespace

from app.price_scheduler import PriceRefreshScheduler


class FakePriceService:
    def __init__(self):
        self.market_hours = SimpleNamespace()
        self.calls = []

    def tracked_symbols(self):
        return ("111111", "222222", "333333")

    def get_price(self, code, force_refresh=False, priority="watchlist"):
        self.calls.append((code, force_refresh, priority))
        if code == "222222":
            raise RuntimeError("Temporary failure")
        return {"ins_code": code}


def test_refresh_once_continues_after_symbol_failure():
    service = FakePriceService()
    scheduler = PriceRefreshScheduler(service)

    refreshed = scheduler.refresh_once()

    assert refreshed == 2
    assert service.calls == [
        ("111111", True, None),
        ("222222", True, None),
        ("333333", True, None),
    ]


def test_refresh_once_with_no_tracked_symbols():
    service = FakePriceService()
    service.tracked_symbols = lambda: ()
    scheduler = PriceRefreshScheduler(service)

    assert scheduler.refresh_once() == 0
    assert service.calls == []


class FakeClock:
    def __init__(self, value=100.0):
        self.value = value

    def __call__(self):
        return self.value


class FakeMarketHours:
    def get_status(self):
        return SimpleNamespace(
            phase="continuous",
            interval_seconds=20,
        )


class DuePriceService:
    def __init__(self, symbols, priorities=None, fail=False):
        self.market_hours = FakeMarketHours()
        self.symbols = tuple(symbols)
        self.priorities = priorities or {}
        self.fail = fail
        self.calls = []

    def tracked_symbols(self):
        return self.symbols

    def symbol_priority(self, code):
        return self.priorities.get(code, "watchlist")

    def get_price(self, code, force_refresh=False, priority=None):
        self.calls.append(code)
        if self.fail:
            raise RuntimeError("Temporary failure")
        return {"ins_code": code}


def test_refresh_due_once_prefers_highest_priority_when_deadlines_match():
    service = DuePriceService(
        ("background", "watchlist", "alert"),
        {
            "background": "background",
            "watchlist": "watchlist",
            "alert": "alert",
        },
    )
    scheduler = PriceRefreshScheduler(service, clock=FakeClock())

    refreshed = scheduler.refresh_due_once()

    assert refreshed == "alert"
    assert service.calls == ["alert"]


def test_refresh_due_once_respects_priority_intervals():
    for priority, interval in (("alert", 20), ("watchlist", 60)):
        clock = FakeClock()
        service = DuePriceService(
            ("111111",),
            {"111111": priority},
        )
        scheduler = PriceRefreshScheduler(service, clock=clock)

        assert scheduler.refresh_due_once() == "111111"

        clock.value += interval - 1
        assert scheduler.refresh_due_once() is None

        clock.value += 1
        assert scheduler.refresh_due_once() == "111111"


def test_refresh_due_once_retries_after_failure():
    clock = FakeClock()
    service = DuePriceService(
        ("111111",),
        {"111111": "alert"},
        fail=True,
    )
    scheduler = PriceRefreshScheduler(service, clock=clock)

    assert scheduler.refresh_due_once() == "111111"
    assert service.calls == ["111111"]

    clock.value += 20
    assert scheduler.refresh_due_once() == "111111"
    assert service.calls == ["111111", "111111"]


def test_refresh_due_once_removes_untracked_symbol_state():
    service = DuePriceService(("111111",))
    scheduler = PriceRefreshScheduler(service, clock=FakeClock())

    assert scheduler.refresh_due_once() == "111111"
    assert "111111" in scheduler._next_due

    service.symbols = ()
    assert scheduler.refresh_due_once() is None
    assert scheduler._next_due == {}
