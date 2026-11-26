import json
import time
import httpx
import pytest

from app.errors import ProviderSchemaError, ProviderUnavailable
from app.providers.tsetmc import TsetmcClient


def test_search_instruments_normalizes_and_preserves_raw():
    def handler(request):
        assert "Instrument/GetInstrumentSearch/" in str(request.url)
        return httpx.Response(200, json={
            "instrumentSearch": [{
                "insCode": "123456789",
                "lVal18AFC": "فولاد",
                "lVal30": "فولاد مبارکه",
                "cIsin": "IRO1TEST0001",
                "flow": 1,
                "flowTitle": "بورس",
                "cgrValCot": "N1",
                "future_field": "preserved",
            }]
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(http_client=client, min_interval=0, max_retries=0)

    result = provider.search_instruments("فولاد")
    client.close()

    assert result[0]["ins_code"] == "123456789"
    assert result[0]["symbol"] == "فولاد"
    assert result[0]["market"] == "بورس"
    assert result[0]["raw"]["future_field"] == "preserved"



def test_search_instruments_normalizes_persian_yeh_and_kaf_for_request():
    def handler(request):
        from urllib.parse import unquote
        assert unquote(request.url.path).endswith("/فملي")
        return httpx.Response(200, json={
            "instrumentSearch": [{
                "insCode": "35425587644337450",
                "lVal18AFC": "فملي",
                "lVal30": "ملی صنایع مس ایران",
                "cgrValCot": "N1",
            }]
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(http_client=client, min_interval=0, max_retries=0)
    result = provider.search_instruments("فملی")
    client.close()

    # Request text is normalized, but the upstream symbol is preserved verbatim.
    assert result[0]["symbol"] == "فملي"


def test_search_instruments_keeps_and_classifies_all_instrument_types():
    rows = [
        {"insCode": "1", "lVal18AFC": "فولاد", "lVal30": "فولاد مبارکه", "cgrValCot": "N1"},
        {"insCode": "2", "lVal18AFC": "سیسکو", "lVal30": "فولاد سیرجان", "cgrValCot": "N2"},
        {"insCode": "3", "lVal18AFC": "ارفع", "lVal30": "شرکت آهن و فولاد ارفع", "cgrValCot": "Z1"},
        {"insCode": "4", "lVal18AFC": "توسکا", "lVal30": "صندوق سرمایه‌گذاری", "cgrValCot": "H1"},
        {"insCode": "5", "lVal18AFC": "صندوق", "lVal30": "صندوق قابل معامله", "cgrValCot": "51"},
        {"insCode": "6", "lVal18AFC": "احیا07", "lVal30": "مرابحه فولاد", "cgrValCot": "17"},
        {"insCode": "7", "lVal18AFC": "تسفا", "lVal30": "توسعه سازه فولاد", "cgrValCot": "OT"},
        {"insCode": "8", "lVal18AFC": "فخاسح", "lVal30": "ح . فولاد خراسان", "cgrValCot": "N2"},
        {"insCode": "9", "lVal18AFC": "فولاژح", "lVal30": "ح.فولاد آلیاژی", "cgrValCot": "N1"},
        {"insCode": "10", "lVal18AFC": "حق", "lVal30": "حق تقدم فولاد", "cgrValCot": "N1"},
        {"insCode": "11", "lVal18AFC": "نامعتبر", "lVal30": "نماد بدون نوع", "cgrValCot": None},
        {"lVal18AFC": "بدون کد", "lVal30": "ابزار بدون کد", "cgrValCot": "UNKNOWN"},
    ]

    def handler(_):
        return httpx.Response(200, json={"instrumentSearch": rows})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(http_client=client, min_interval=0, max_retries=0)
    result = provider.search_instruments("فولاد")
    client.close()

    assert len(result) == len(rows)
    assert [item["instrument_category"] for item in result] == [
        "COMMON_STOCK", "COMMON_STOCK", "COMMON_STOCK",
        "FUND", "FUND", "DEBT", "OTHER",
        "RIGHTS", "RIGHTS", "RIGHTS", "OTHER", "OTHER",
    ]
    assert [item["instrument_category_label"] for item in result] == [
        "سهام", "سهام", "سهام", "صندوق", "صندوق", "اوراق بدهی",
        "سایر", "حق‌تقدم", "حق‌تقدم", "حق‌تقدم", "سایر", "سایر",
    ]
    assert result[0]["instrument_type"] == "N1"
    assert result[3]["instrument_type"] == "H1"
    assert result[5]["instrument_type"] == "17"
    assert result[6]["instrument_type"] == "OT"
    assert result[10]["instrument_type"] is None
    assert result[11]["ins_code"] is None
    assert result[6]["raw"] == rows[6]


def test_common_stock_name_containing_ha_is_not_misclassified_as_rights():
    row = {
        "lVal18AFC": "فولاد",
        "lVal30": "شرکت فولاد حامی",
        "cgrValCot": "N1",
    }
    assert TsetmcClient._classify_instrument(row) == (
        "N1", "COMMON_STOCK", "سهام"
    )


def test_search_raises_on_schema_change():
    def handler(_):
        return httpx.Response(200, json={"unexpected": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(http_client=client, min_interval=0, max_retries=0)

    with pytest.raises(ProviderSchemaError):
        provider.search_instruments("فولاد")

    client.close()


def test_get_instrument_info_normalizes_and_preserves_raw():
    def handler(request):
        assert "Instrument/GetInstrumentInfo/123456789" in str(request.url)
        return httpx.Response(200, json={
            "instrumentInfo": {
                "insCode": "123456789",
                "lVal18AFC": "فولاد",
                "lVal30": "فولاد مبارکه",
                "cIsin": "IRO1TEST0001",
                "flowTitle": "بورس",
                "cgrValCot": "N1",
                "sector": {"lSecVal": "فلزات اساسی"},
                "eps": {"estimatedEPS": "693", "sectorPE": 11.34},
                "qTotTran5JAvg": 2592568573.0,
                "future_field": "preserved",
            }
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(http_client=client, min_interval=0, max_retries=0)

    result = provider.get_instrument_info("123456789")
    client.close()

    assert result["symbol"] == "فولاد"
    assert result["name"] == "فولاد مبارکه"
    assert result["sector"] == "فلزات اساسی"
    assert result["instrument_type"] == "N1"
    assert result["instrument_category"] == "COMMON_STOCK"
    assert result["instrument_category_label"] == "سهام"
    assert result["eps"]["estimatedEPS"] == "693"
    assert result["fundamentals"] == {
        "eps_actual": None,
        "eps_estimated": 693.0,
        "sector_pe": 11.34,
    }
    assert result["average_volume"] == 2592568573
    assert type(result["average_volume"]) is int
    assert result["raw"]["future_field"] == "preserved"


def test_get_instrument_info_rejects_invalid_fundamental_numbers():
    def handler(_):
        return httpx.Response(200, json={
            "instrumentInfo": {
                "insCode": "123456789",
                "lVal18AFC": "نماد",
                "lVal30": "شرکت نمونه",
                "cgrValCot": "N1",
                "eps": {
                    "epsValue": True,
                    "estimatedEPS": "NaN",
                    "sectorPE": "نامعتبر",
                },
            }
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(http_client=client, min_interval=0, max_retries=0)
    result = provider.get_instrument_info("123456789")
    client.close()

    assert result["fundamentals"] == {
        "eps_actual": None,
        "eps_estimated": None,
        "sector_pe": None,
    }


def test_get_instrument_info_raises_on_schema_change():
    def handler(_):
        return httpx.Response(200, json={"unexpected": {}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(http_client=client, min_interval=0, max_retries=0)

    with pytest.raises(ProviderSchemaError):
        provider.get_instrument_info("123456789")

    client.close()


def test_get_closing_price_info_normalizes_response():
    def handler(request):
        assert "ClosingPrice/GetClosingPriceInfo/123456789" in str(request.url)
        return httpx.Response(200, json={
            "closingPriceInfo": {
                "finalLastDate": 20261114,
                "pClosing": 5020,
                "pDrCotVal": 5090,
                "priceFirst": 4860,
                "priceMin": 4810,
                "priceMax": 5090,
                "priceYesterday": 4950,
                "zTotTran": 40406,
                "qTotTran5J": 4097617753,
                "qTotCap": 20568684791350,
                "instrumentState": {"cEtavalTitle": "مجاز"},
            }
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(http_client=client, min_interval=0, max_retries=0)

    result = provider.get_closing_price_info("123456789")
    client.close()

    assert result["ins_code"] == "123456789"
    assert result["closing_price"] == 5020
    assert result["last_price"] == 5090
    assert result["trade_count"] == 40406
    assert result["volume"] == 4097617753
    assert result["value"] == 20568684791350
    assert result["state"] == "مجاز"


def test_get_daily_prices_normalizes_and_preserves_raw():
    def handler(request):
        assert "ClosingPrice/GetClosingPriceDailyList/123456789/365" in str(request.url)
        return httpx.Response(200, json={
            "closingPriceDaily": [{
                "dEven": 20261114,
                "priceChange": 140,
                "priceMin": 4810,
                "priceMax": 5090,
                "priceYesterday": 4950,
                "priceFirst": 4860,
                "pClosing": 5020,
                "pDrCotVal": 5090,
                "zTotTran": 40406,
                "qTotTran5J": 4097617753,
                "qTotCap": 20568684791350,
                "future_field": "preserved",
            }]
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(http_client=client, min_interval=0, max_retries=0)

    result = provider.get_daily_prices("123456789", 5)
    client.close()

    assert len(result) == 1
    assert result[0]["date"] == 20261114
    assert result[0]["change"] == 140
    assert result[0]["closing_price"] == 5020
    assert result[0]["raw"]["future_field"] == "preserved"


def test_get_daily_prices_raises_on_schema_change():
    def handler(_):
        return httpx.Response(200, json={"unexpected": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(http_client=client, min_interval=0, max_retries=0)

    with pytest.raises(ProviderSchemaError):
        provider.get_daily_prices("123456789", 5)

    client.close()



def test_get_daily_prices_sorts_deduplicates_and_skips_invalid_dates():
    def handler(request):
        assert "ClosingPrice/GetClosingPriceDailyList/123456789/365" in str(request.url)
        return httpx.Response(200, json={
            "closingPriceDaily": [
                {"dEven": 20261114, "pClosing": 140},
                {"dEven": 20261112, "pClosing": 120},
                {"dEven": 20261113, "pClosing": 130},
                {"dEven": 20261113, "pClosing": 135},
                {"dEven": "invalid", "pClosing": 999},
                {"dEven": 20260230, "pClosing": 888},
            ]
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(http_client=client, min_interval=0, max_retries=0)

    result = provider.get_daily_prices("123456789", 2)
    client.close()

    assert [item["date"] for item in result] == [20261113, 20261114]
    assert [item["closing_price"] for item in result] == [135, 140]


def test_daily_prices_cache_reuses_history_and_returns_independent_data():
    calls = 0

    def handler(_):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={
            "closingPriceDaily": [
                {"dEven": 20261113, "pClosing": 130},
                {"dEven": 20261114, "pClosing": 140},
            ]
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(
        http_client=client, min_interval=0, max_retries=0
    )

    first = provider.get_daily_prices("123456789", 2)
    first[0]["closing_price"] = -1
    second = provider.get_daily_prices("123456789", 1)

    assert calls == 1
    assert second[0]["closing_price"] == 140

    client.close()


def test_daily_prices_cache_expires():
    calls = 0

    def handler(_):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={
            "closingPriceDaily": [
                {"dEven": 20261114, "pClosing": 100 + calls}
            ]
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(
        http_client=client,
        min_interval=0,
        max_retries=0,
        history_cache_ttl=0.01,
    )

    first = provider.get_daily_prices("123456789", 1)
    time.sleep(0.02)
    second = provider.get_daily_prices("123456789", 1)

    assert calls == 2
    assert first[0]["closing_price"] == 101
    assert second[0]["closing_price"] == 102

    client.close()


def test_daily_prices_cache_is_shared_between_different_counts():
    calls = 0

    def handler(_):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={
            "closingPriceDaily": [
                {"dEven": 20261112, "pClosing": 120},
                {"dEven": 20261113, "pClosing": 130},
                {"dEven": 20261114, "pClosing": 140},
            ]
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(
        http_client=client, min_interval=0, max_retries=0
    )

    short = provider.get_daily_prices("123456789", 1)
    long = provider.get_daily_prices("123456789", 3)

    assert calls == 1
    assert len(short) == 1
    assert len(long) == 3

    client.close()


def test_daily_prices_cache_prevents_duplicate_concurrent_requests():
    import threading

    calls = 0
    calls_lock = threading.Lock()
    barrier = threading.Barrier(5)

    def handler(_):
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.03)
        return httpx.Response(200, json={
            "closingPriceDaily": [
                {"dEven": 20261114, "pClosing": 140}
            ]
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(
        http_client=client, min_interval=0, max_retries=0
    )
    results = []
    errors = []

    def worker():
        try:
            barrier.wait()
            results.append(provider.get_daily_prices("123456789", 1))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert len(results) == 5
    assert calls == 1
    assert all(result[0]["closing_price"] == 140 for result in results)
    assert provider._history_key_locks == {}

    client.close()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_retries": -1},
        {"max_retries": 1.5},
        {"max_retries": True},
        {"min_interval": -0.1},
        {"min_interval": float("inf")},
        {"history_cache_ttl": -1},
        {"history_cache_ttl": float("nan")},
        {"history_cache_max_entries": 0},
        {"history_cache_max_entries": 1.5},
        {"history_cache_max_entries": True},
    ],
)
def test_client_rejects_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        TsetmcClient(**kwargs)


@pytest.mark.parametrize("ins_code", ["", " ", "\t"])
def test_daily_prices_rejects_empty_instrument_code(ins_code):
    provider = TsetmcClient(min_interval=0, max_retries=0)

    with pytest.raises(ValueError, match="instrument code"):
        provider.get_daily_prices(ins_code)


@pytest.mark.parametrize("invalid", [None, 123, [], {}, "", "   "])
@pytest.mark.parametrize(
    "method_name",
    [
        "search_instruments",
        "get_instrument_info",
        "get_closing_price_info",
        "get_daily_prices",
    ],
)
def test_public_methods_reject_invalid_string_inputs(method_name, invalid):
    provider = TsetmcClient(min_interval=0, max_retries=0)
    method = getattr(provider, method_name)

    with pytest.raises(ValueError):
        method(invalid)


def test_client_uses_configured_default_interval_and_retries(monkeypatch):
    import app.providers.tsetmc as tsetmc_module

    monkeypatch.setattr(tsetmc_module.settings, "tsetmc_min_interval_seconds", 0.25)
    monkeypatch.setattr(tsetmc_module.settings, "tsetmc_max_retries", 4)

    provider = TsetmcClient()

    assert provider._min_interval == 0.25
    assert provider._max_retries == 4


def test_client_uses_configured_timeout(monkeypatch):
    import app.providers.tsetmc as tsetmc_module

    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(tsetmc_module.settings, "tsetmc_timeout_seconds", 7.5)
    monkeypatch.setattr(tsetmc_module.httpx, "Client", FakeClient)

    provider = TsetmcClient()
    provider.start()

    assert captured["timeout"] == 7.5


def test_client_retries_using_configured_retry_count(monkeypatch):
    import app.providers.tsetmc as tsetmc_module

    calls = 0

    def handler(_):
        nonlocal calls
        calls += 1

        if calls == 1:
            return httpx.Response(503)

        return httpx.Response(200, json={"status": "ok"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(tsetmc_module.settings, "tsetmc_min_interval_seconds", 0)
    monkeypatch.setattr(tsetmc_module.settings, "tsetmc_max_retries", 1)
    monkeypatch.setattr(tsetmc_module.time, "sleep", lambda _: None)

    provider = TsetmcClient(http_client=client)

    try:
        result = provider._get_json("test")
    finally:
        client.close()

    assert result == {"status": "ok"}
    assert calls == 2


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("DNS resolution failed"),
        httpx.ReadTimeout("Upstream response timed out"),
    ],
)
def test_client_retries_network_and_timeout_errors(error, monkeypatch):
    import app.providers.tsetmc as tsetmc_module
    from app.errors import ProviderUnavailable

    calls = 0

    def handler(_):
        nonlocal calls
        calls += 1
        raise error

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(tsetmc_module.time, "sleep", lambda _: None)

    provider = TsetmcClient(
        http_client=client,
        min_interval=0,
        max_retries=2,
    )

    try:
        with pytest.raises(ProviderUnavailable):
            provider._get_json("test")
    finally:
        client.close()

    assert calls == 3


def test_get_json_does_not_follow_redirects():
    requested_urls = []

    def handler(request):
        requested_urls.append(str(request.url))
        return httpx.Response(
            302,
            headers={"Location": "http://127.0.0.1/internal"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    provider = TsetmcClient(
        http_client=client,
        min_interval=0,
        max_retries=0,
    )

    try:
        with pytest.raises(ProviderUnavailable):
            provider._get_json("test")
        assert len(requested_urls) == 1
        assert "127.0.0.1" not in requested_urls[0]
    finally:
        client.close()


@pytest.mark.parametrize("path", [
    "",
    None,
    123,
    "https://evil.example/steal",
    "//evil.example/steal",
    "/Instrument/GetInstrumentInfo/123",
    "../internal",
    "Instrument/../../internal",
    "Instrument/%2e%2e/internal",
    "Instrument/%2E%2E/internal",
    r"Instrument\..\internal",
    "Instrument/GetInfo?redirect=http://evil.example",
    "Instrument/GetInfo#fragment",
    "Instrument/invalid path",
])
def test_get_json_rejects_unsafe_paths_before_request(path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(
        http_client=client,
        min_interval=0,
        max_retries=0,
    )

    try:
        with pytest.raises(ValueError):
            provider._get_json(path)

        assert calls == []
    finally:
        client.close()


@pytest.mark.parametrize("status_code", [401, 404])
def test_client_does_not_retry_permanent_http_errors(status_code, monkeypatch):
    import app.providers.tsetmc as tsetmc_module

    calls = 0

    def handler(_):
        nonlocal calls
        calls += 1
        return httpx.Response(status_code)

    monkeypatch.setattr(tsetmc_module.time, "sleep", lambda _: None)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(http_client=client, min_interval=0, max_retries=3)

    try:
        with pytest.raises(ProviderUnavailable):
            provider._get_json("test")
        assert calls == 1
    finally:
        client.close()


def test_daily_prices_releases_key_lock_after_request_failure():
    from app.errors import ProviderUnavailable

    def handler(_):
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(
        http_client=client,
        min_interval=0,
        max_retries=0,
    )

    try:
        with pytest.raises(ProviderUnavailable):
            provider.get_daily_prices("123456789", 1)

        assert provider._history_key_locks == {}
    finally:
        client.close()


@pytest.mark.parametrize("status_code", [429, 500, 502, 504])
def test_client_retries_transient_http_statuses(status_code, monkeypatch):
    import app.providers.tsetmc as tsetmc_module

    calls = 0

    def handler(_):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(status_code)
        return httpx.Response(200, json={"status": "ok"})

    monkeypatch.setattr(tsetmc_module.time, "sleep", lambda _: None)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(
        http_client=client,
        min_interval=0,
        max_retries=1,
    )

    try:
        result = provider._get_json("test")
    finally:
        client.close()

    assert result == {"status": "ok"}
    assert calls == 2


def test_closing_price_info_rejects_invalid_numeric_values_and_sanitizes_raw():
    def handler(_):
        return httpx.Response(200, content=json.dumps({
            "closingPriceInfo": {
                "finalLastDate": 20261114,
                "pClosing": -1,
                "pDrCotVal": 12.5,
                "priceFirst": float("nan"),
                "priceMin": float("inf"),
                "priceMax": "NaN",
                "priceYesterday": 2**63,
                "zTotTran": True,
                "qTotTran5J": -10,
                "qTotCap": 20568684791350,
                "future_field": "preserved",
            }
        }, allow_nan=True).encode(), headers={"Content-Type": "application/json"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(http_client=client, min_interval=0, max_retries=0)
    try:
        result = provider.get_closing_price_info("123456789")
    finally:
        client.close()

    for field in (
        "closing_price", "last_price", "first_price", "min_price",
        "max_price", "yesterday_price", "trade_count", "volume",
    ):
        assert result[field] is None

    assert result["value"] == 20568684791350
    assert result["raw"]["priceFirst"] is None
    assert result["raw"]["priceMin"] is None
    assert result["raw"]["future_field"] == "preserved"


def test_daily_prices_rejects_invalid_numeric_values_and_sanitizes_raw():
    def handler(_):
        return httpx.Response(200, content=json.dumps({
            "closingPriceDaily": [{
                "dEven": 20261114,
                "priceChange": 12.5,
                "pClosing": -1,
                "pDrCotVal": float("inf"),
                "priceFirst": "12.5",
                "priceMin": True,
                "priceMax": 2**63,
                "priceYesterday": 4950,
                "zTotTran": -1,
                "qTotTran5J": 4097617753,
                "qTotCap": float("nan"),
                "future_field": "preserved",
            }]
        }, allow_nan=True).encode(), headers={"Content-Type": "application/json"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TsetmcClient(http_client=client, min_interval=0, max_retries=0)
    try:
        result = provider.get_daily_prices("123456789", 5)
    finally:
        client.close()

    assert len(result) == 1
    item = result[0]

    for field in (
        "change", "closing_price", "last_price", "first_price",
        "min_price", "max_price", "trade_count", "value",
    ):
        assert item[field] is None

    assert item["date"] == 20261114
    assert item["yesterday_price"] == 4950
    assert item["volume"] == 4097617753
    assert item["raw"]["pDrCotVal"] is None
    assert item["raw"]["qTotCap"] is None
    assert item["raw"]["future_field"] == "preserved"
