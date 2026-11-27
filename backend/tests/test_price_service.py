from datetime import datetime, timezone

import pytest

from app.errors import ProviderUnavailable
from app.price_service import PriceDataService


class FakeMarketStatus:
    phase = "continuous"
    interval_seconds = 20


class FakeMarketHours:
    def get_status(self):
        return FakeMarketStatus()


class FakeProvider:
    def __init__(self):
        self.calls = 0
        self.should_fail = False

    def get_closing_price_info(self, code):
        self.calls += 1
        if self.should_fail:
            raise ProviderUnavailable("TSETMC unavailable")
        return {"ins_code": code, "closing_price": 5020}


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value


def make_service():
    provider = FakeProvider()
    clock = FakeClock()
    service = PriceDataService(
        provider=provider,
        market_hours=FakeMarketHours(),
        clock=clock,
        utcnow=lambda: datetime(2026, 11, 17, 6, 0, tzinfo=timezone.utc),
    )
    return service, provider, clock


def test_first_request_fetches_without_background_tracking():
    service, provider, _ = make_service()

    result = service.get_price("123456789")

    assert provider.calls == 1
    assert result["item"]["closing_price"] == 5020
    assert result["data_status"] == "fresh"
    assert result["market_phase"] == "continuous"
    assert service.tracked_symbols() == ()


def test_fresh_cache_avoids_repeated_provider_request():
    service, provider, clock = make_service()

    first = service.get_price("123456789")
    clock.value += 5
    second = service.get_price("123456789")

    assert provider.calls == 1
    assert second["item"] == first["item"]
    assert second["retrieved_at"] == first["retrieved_at"]


def test_expired_cache_is_refreshed():
    service, provider, clock = make_service()

    service.register_symbol("123456789", "watchlist")
    service.get_price("123456789")
    clock.value += 61
    service.get_price("123456789")

    assert provider.calls == 2


def test_provider_error_returns_last_valid_cached_price(caplog):
    service, provider, clock = make_service()

    service.register_symbol("123456789", "watchlist")
    service.get_price("123456789")
    clock.value += 61
    provider.should_fail = True

    result = service.get_price("123456789")

    assert provider.calls == 2
    assert result["item"]["closing_price"] == 5020
    assert result["data_status"] == "stale"
    assert result["last_error"] == "Price provider temporarily unavailable."
    assert "TSETMC unavailable" not in result["last_error"]
    assert "TSETMC unavailable" in caplog.text


def test_provider_error_without_cache_is_propagated():
    service, provider, _ = make_service()
    provider.should_fail = True

    with pytest.raises(ProviderUnavailable):
        service.get_price("123456789")


def test_force_refresh_bypasses_fresh_cache():
    service, provider, _ = make_service()

    service.get_price("123456789")
    service.get_price("123456789", force_refresh=True)

    assert provider.calls == 2


def test_cached_item_is_not_mutated_by_caller():
    service, provider, _ = make_service()

    first = service.get_price("123456789")
    first["item"]["closing_price"] = -1
    second = service.get_price("123456789")

    assert second["item"]["closing_price"] == 5020
    assert provider.calls == 1



def test_normal_request_does_not_downgrade_alert_priority():
    service, _, _ = make_service()
    service.register_symbol("123456789", "alert")

    service.get_price("123456789")

    assert service.symbol_priority("123456789") == "alert"


def test_background_cache_uses_its_own_refresh_interval():
    service, provider, clock = make_service()
    service.register_symbol("123456789", "background")

    service.get_price("123456789", priority=None)
    clock.value += 30
    service.get_price("123456789", priority=None)

    assert provider.calls == 1



def test_symbol_remains_tracked_until_all_sources_are_removed():
    service, _, _ = make_service()

    service.register_symbol("123456789", "watchlist")
    service.register_symbol("123456789", "alert")

    assert service.symbol_priority("123456789") == "alert"
    assert service.unregister_symbol("123456789", "alert") is False
    assert service.symbol_priority("123456789") == "watchlist"
    assert service.tracked_symbols() == ("123456789",)

    assert service.unregister_symbol("123456789", "watchlist") is True
    assert service.tracked_symbols() == ()


def test_unregistering_one_source_preserves_other_sources():
    service, _, _ = make_service()

    service.register_symbol("123456789", "background")
    service.register_symbol("123456789", "watchlist")

    service.unregister_symbol("123456789", "watchlist")

    assert service.symbol_sources("123456789") == ("background",)
    assert service.symbol_priority("123456789") == "background"


def test_untracked_price_request_keeps_cache_but_does_not_track_symbol():
    service, provider, _ = make_service()

    first = service.get_price("123456789")
    second = service.get_price("123456789")

    assert first["item"] == second["item"]
    assert provider.calls == 1
    assert service.tracked_symbols() == ()


def test_explicit_priority_request_registers_source():
    service, _, _ = make_service()

    service.get_price("123456789", priority="alert")

    assert service.tracked_symbols() == ("123456789",)
    assert service.symbol_sources("123456789") == ("alert",)



def test_cache_is_bounded_and_evicts_least_recently_used_entry():
    provider = FakeProvider()
    service = PriceDataService(
        provider=provider,
        market_hours=FakeMarketHours(),
        cache_max_entries=2,
    )

    service.get_price("111")
    service.get_price("222")
    service.get_price("111")  # Make 111 the most recently used entry.
    service.get_price("333")

    assert tuple(service._cache) == ("111", "333")
    assert len(service._cache) == 2


def test_cache_capacity_must_be_positive_integer():
    provider = FakeProvider()
    for invalid in (0, -1, 1.5, True):
        with pytest.raises(ValueError, match="positive integer"):
            PriceDataService(
                provider=provider,
                market_hours=FakeMarketHours(),
                cache_max_entries=invalid,
            )


def test_symbol_lock_registry_is_cleaned_after_request():
    service, _, _ = make_service()

    service.get_price("123456789")

    assert service._symbol_locks == {}


def test_concurrent_same_symbol_requests_share_one_provider_call():
    import threading
    from concurrent.futures import ThreadPoolExecutor

    class BlockingProvider(FakeProvider):
        def __init__(self):
            super().__init__()
            self.entered = threading.Event()
            self.release = threading.Event()

        def get_closing_price_info(self, code):
            self.calls += 1
            self.entered.set()
            assert self.release.wait(timeout=3)
            return {"ins_code": code, "closing_price": 5020}

    provider = BlockingProvider()
    service = PriceDataService(
        provider=provider,
        market_hours=FakeMarketHours(),
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service.get_price, "123456789")
        assert provider.entered.wait(timeout=2)
        second = pool.submit(service.get_price, "123456789")
        provider.release.set()
        first_result = first.result(timeout=3)
        second_result = second.result(timeout=3)

    assert provider.calls == 1
    assert first_result["item"] == second_result["item"]
    assert service._symbol_locks == {}
