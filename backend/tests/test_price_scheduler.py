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
    def __init__(self, symbols, priorities=None, fail=False, stale=False):
        self.market_hours = FakeMarketHours()
        self.symbols = tuple(symbols)
        self.priorities = priorities or {}
        self.fail = fail
        self.stale = stale
        self.calls = []

    def tracked_symbols(self):
        return self.symbols

    def symbol_priority(self, code):
        return self.priorities.get(code, "watchlist")

    def get_price(self, code, force_refresh=False, priority=None):
        self.calls.append(code)
        if self.fail:
            raise RuntimeError("Temporary failure")
        return {
            "ins_code": code,
            "data_status": "stale" if self.stale else "fresh",
        }


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


def test_refresh_due_once_retries_stale_cache_after_short_delay():
    clock = FakeClock()
    service = DuePriceService(
        ("111111",),
        {"111111": "alert"},
        stale=True,
    )
    scheduler = PriceRefreshScheduler(service, clock=clock)

    assert scheduler.refresh_due_once() == "111111"
    assert service.calls == ["111111"]

    clock.value += 4
    assert scheduler.refresh_due_once() is None

    clock.value += 1
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


class ControlledThread:
    instances = []

    def __init__(self, target, name, daemon):
        self.target = target
        self.name = name
        self.daemon = daemon
        self.alive = False
        self.join_calls = []
        self.finish_on_join = True
        type(self).instances.append(self)

    def start(self):
        self.alive = True

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.join_calls.append(timeout)
        if self.finish_on_join:
            self.alive = False


def test_start_is_idempotent_and_stop_allows_restart(monkeypatch):
    import app.price_scheduler as scheduler_module

    ControlledThread.instances = []
    monkeypatch.setattr(
        scheduler_module.threading, "Thread", ControlledThread
    )

    scheduler = PriceRefreshScheduler(DuePriceService(("111111",)))

    scheduler.start()
    scheduler.start()

    assert len(ControlledThread.instances) == 1
    first = ControlledThread.instances[0]
    assert first.alive is True

    scheduler.stop(timeout=2)

    assert first.join_calls == [2]
    assert first.alive is False
    assert scheduler._stop_event.is_set()

    scheduler.start()

    assert len(ControlledThread.instances) == 2
    second = ControlledThread.instances[1]
    assert second.alive is True
    assert scheduler._stop_event.is_set() is False

    scheduler.stop()


def test_start_does_not_spawn_second_thread_if_stop_times_out(monkeypatch):
    import app.price_scheduler as scheduler_module

    ControlledThread.instances = []
    monkeypatch.setattr(
        scheduler_module.threading, "Thread", ControlledThread
    )

    scheduler = PriceRefreshScheduler(DuePriceService(("111111",)))
    scheduler.start()

    first = ControlledThread.instances[0]
    first.finish_on_join = False

    scheduler.stop(timeout=0.01)

    assert first.alive is True
    assert len(ControlledThread.instances) == 1

    scheduler.start()

    assert len(ControlledThread.instances) == 1
    assert first.alive is True


def test_start_recovers_if_thread_start_raises(monkeypatch):
    import app.price_scheduler as scheduler_module

    class FailingThread(ControlledThread):
        def start(self):
            raise RuntimeError("thread start failed")

    monkeypatch.setattr(
        scheduler_module.threading, "Thread", FailingThread
    )

    scheduler = PriceRefreshScheduler(DuePriceService(("111111",)))

    import pytest

    with pytest.raises(RuntimeError, match="thread start failed"):
        scheduler.start()

    assert scheduler._thread is None
    assert scheduler._stop_event.is_set()


def test_stop_rejects_negative_timeout():
    import pytest

    scheduler = PriceRefreshScheduler(DuePriceService(("111111",)))

    with pytest.raises(ValueError, match="non-negative"):
        scheduler.stop(timeout=-1)
