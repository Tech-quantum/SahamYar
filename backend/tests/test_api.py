import pytest
from datetime import date, timedelta
import app.main as main
from app.errors import ProviderUnavailable
from app.price_service import PriceDataService


@pytest.fixture(autouse=True)
def default_common_stock_instrument(monkeypatch):
    monkeypatch.setattr(
        main.tsetmc,
        "get_instrument_info",
        lambda code: {
            "ins_code": code,
            "instrument_category": "COMMON_STOCK",
            "instrument_category_label": "سهام",
        },
    )


def test_health():
    response = main.app.test_client().get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_search_rejects_short_query():
    response = main.app.test_client().get("/api/v1/stocks/search?q=a")
    assert response.status_code == 400


def test_search_returns_results(monkeypatch):
    monkeypatch.setattr(
        main.tsetmc,
        "search_instruments",
        lambda query: [{"symbol": "فولاد", "name": "فولاد مبارکه"}],
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/search?q=فولاد"
    )

    assert response.status_code == 200
    assert response.json["count"] == 1
    assert response.json["items"][0]["symbol"] == "فولاد"


def test_search_handles_provider_error(monkeypatch):
    def fail(_):
        raise ProviderUnavailable("Upstream unavailable")

    monkeypatch.setattr(main.tsetmc, "search_instruments", fail)

    response = main.app.test_client().get(
        "/api/v1/stocks/search?q=فولاد"
    )

    assert response.status_code == 502


def test_instrument_info_returns_details(monkeypatch):
    monkeypatch.setattr(
        main.tsetmc,
        "get_instrument_info",
        lambda code: {
            "ins_code": code,
            "symbol": "فولاد",
            "name": "فولاد مبارکه",
            "sector": "فلزات اساسی",
            "eps": {"estimatedEPS": "693"},
            "fundamentals": {
                "eps_actual": None,
                "eps_estimated": 693.0,
                "sector_pe": 11.34,
            },
            "average_volume": 2592568573,
        },
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789"
    )

    assert response.status_code == 200
    assert response.json["source"] == "TSETMC"
    assert response.json["item"]["symbol"] == "فولاد"
    assert response.json["item"]["average_volume"] == 2592568573
    assert type(response.json["item"]["average_volume"]) is int
    assert response.json["item"]["fundamentals"]["eps_estimated"] == 693.0
    assert response.json["item"]["fundamentals"]["sector_pe"] == 11.34


def test_instrument_info_rejects_invalid_code():
    response = main.app.test_client().get("/api/v1/stocks/abc")

    assert response.status_code == 400


def test_instrument_info_handles_provider_error(monkeypatch):
    def fail(_):
        raise ProviderUnavailable("Upstream unavailable")

    monkeypatch.setattr(main.tsetmc, "get_instrument_info", fail)

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789"
    )

    assert response.status_code == 502


def test_stock_prices_returns_closing_info(monkeypatch):
    monkeypatch.setattr(main, 'price_service', PriceDataService(main.tsetmc))
    monkeypatch.setattr(
        main.tsetmc,
        "get_closing_price_info",
        lambda code: {
            "ins_code": code,
            "closing_price": 5020,
            "last_price": 5090,
            "volume": 4097617753,
        },
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/prices"
    )

    assert response.status_code == 200
    assert response.json["source"] == "TSETMC"
    assert response.json["item"]["closing_price"] == 5020



def test_stock_prices_reuses_cache_between_api_requests(monkeypatch):
    calls = []

    def fake_price(code):
        calls.append(code)
        return {
            "ins_code": code,
            "closing_price": 5020,
            "last_price": 5090,
        }

    service = PriceDataService(main.tsetmc, clock=lambda: 100.0)
    monkeypatch.setattr(main, "price_service", service)
    monkeypatch.setattr(
        main.tsetmc,
        "get_closing_price_info",
        fake_price,
    )

    client = main.app.test_client()
    first = client.get("/api/v1/stocks/123456789/prices")
    second = client.get("/api/v1/stocks/123456789/prices")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json["data_status"] == "fresh"
    assert second.json["data_status"] == "fresh"
    assert first.json["item"]["closing_price"] == 5020
    assert second.json["item"]["closing_price"] == 5020
    assert calls == ["123456789"]

def test_stock_prices_rejects_invalid_code():
    response = main.app.test_client().get(
        "/api/v1/stocks/abc/prices"
    )
    assert response.status_code == 400


def test_stock_prices_handles_provider_error(monkeypatch):
    monkeypatch.setattr(main, 'price_service', PriceDataService(main.tsetmc))
    def fail(_):
        raise ProviderUnavailable("Upstream unavailable")

    monkeypatch.setattr(main.tsetmc, "get_closing_price_info", fail)

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/prices"
    )
    assert response.status_code == 502


def test_stock_history_returns_daily_items(monkeypatch):
    def fake_history(code, count):
        assert code == "123456789"
        assert count == 5
        return [{"date": 20261114, "closing_price": 5020}]

    monkeypatch.setattr(main.tsetmc, "get_daily_prices", fake_history)

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/history?count=5"
    )

    assert response.status_code == 200
    assert response.json["count"] == 1
    assert response.json["items"][0]["date"] == 20261114


def test_stock_history_rejects_invalid_count():
    client = main.app.test_client()

    for count in ("abc", "0", "366", "-5"):
        response = client.get(
            f"/api/v1/stocks/123456789/history?count={count}"
        )
        assert response.status_code == 400


def test_stock_history_handles_provider_error(monkeypatch):
    def fail(code, count):
        raise ProviderUnavailable("Upstream unavailable")

    monkeypatch.setattr(main.tsetmc, "get_daily_prices", fail)

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/history"
    )
    assert response.status_code == 502


@pytest.mark.parametrize(
    ("category", "label"),
    [
        ("FUND", "صندوق"),
        ("DEBT", "اوراق بدهی"),
        ("OTHER", "سایر"),
        (None, "سایر"),
    ],
)
def test_stock_analysis_rejects_non_equity_instruments(
    monkeypatch, category, label
):
    monkeypatch.setattr(
        main.tsetmc,
        "get_instrument_info",
        lambda code: {
            "ins_code": code,
            "instrument_category": category,
            "instrument_category_label": label,
        },
    )

    def forbidden_history(*args):
        pytest.fail("History must not be fetched for unsupported instruments")

    monkeypatch.setattr(main.tsetmc, "get_daily_prices", forbidden_history)

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/analysis"
    )

    assert response.status_code == 200
    assert response.json["analysis_status"] == "NOT_SUPPORTED"
    assert response.json["recommendation"]["action"] == "NOT_SUPPORTED"
    assert response.json["indicators"] is None
    assert response.json["layers"]["stock"]["technical"]["status"] == "NOT_SUPPORTED"
    assert label in response.json["recommendation"]["reason"]


def test_stock_analysis_allows_rights_instrument(monkeypatch):
    monkeypatch.setattr(
        main.tsetmc,
        "get_instrument_info",
        lambda code: {
            "ins_code": code,
            "instrument_category": "RIGHTS",
            "instrument_category_label": "حق‌تقدم",
        },
    )
    monkeypatch.setattr(
        main.tsetmc,
        "get_daily_prices",
        lambda code, count: [
            {"date": 20261113, "closing_price": 100},
            {"date": 20261114, "closing_price": 110},
        ],
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/analysis"
    )

    assert response.status_code == 200
    assert response.json["analysis_status"] == "PARTIAL"
    assert response.json["count"] == 2


def test_stock_analysis_returns_indicators(monkeypatch):
    def fake_history(code, count):
        assert code == "123456789"
        assert count == 365
        return [
            {"date": int((date(2026, 11, 14) - timedelta(days=i)).strftime("%Y%m%d")), "closing_price": 100 + i}
            for i in range(250)
        ]

    monkeypatch.setattr(main.tsetmc, "get_daily_prices", fake_history)

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/analysis"
    )

    assert response.status_code == 200
    assert response.json["source"] == "TSETMC"
    assert response.json["count"] == 250
    assert response.json["indicators"]["sma"]["20"] is not None
    assert response.json["indicators"]["sma"]["200"] is not None
    assert response.json["indicators"]["rsi"]["14"] == 0


def test_stock_analysis_sorts_history(monkeypatch):
    monkeypatch.setattr(
        main.tsetmc,
        "get_daily_prices",
        lambda code, count: [
            {"date": 20261114, "closing_price": 300},
            {"date": 20261112, "closing_price": 100},
            {"date": 20261113, "closing_price": 200},
        ],
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/analysis"
    )

    assert response.status_code == 200
    assert response.json["latest_date"] == 20261114
    assert response.json["count"] == 3


def test_stock_analysis_handles_insufficient_history(monkeypatch):
    monkeypatch.setattr(
        main.tsetmc,
        "get_daily_prices",
        lambda code, count: [
            {"date": 20261114, "closing_price": 100},
            {"date": 20261113, "closing_price": 110},
        ],
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/analysis"
    )

    assert response.status_code == 200
    assert response.json["indicators"]["sma"]["20"] is None
    assert response.json["indicators"]["sma"]["200"] is None
    assert response.json["indicators"]["rsi"]["14"] is None


def test_stock_analysis_rejects_invalid_inputs():
    client = main.app.test_client()

    assert client.get("/api/v1/stocks/abc/analysis").status_code == 400

    for count in ("abc", "0", "366", "-5"):
        response = client.get(
            f"/api/v1/stocks/123456789/analysis?count={count}"
        )
        assert response.status_code == 400


def test_stock_analysis_handles_provider_error(monkeypatch):
    def fail(code, count):
        raise ProviderUnavailable("Upstream unavailable")

    monkeypatch.setattr(main.tsetmc, "get_daily_prices", fail)

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/analysis"
    )

    assert response.status_code == 502


def test_stock_analysis_handles_provider_schema_error(monkeypatch):
    from app.errors import ProviderSchemaError

    def fail(code, count):
        raise ProviderSchemaError("Invalid TSETMC response")

    monkeypatch.setattr(main.tsetmc, "get_daily_prices", fail)

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/analysis"
    )

    assert response.status_code == 502
    assert response.json["detail"] == "Invalid TSETMC response"


def test_stock_analysis_ignores_invalid_prices(monkeypatch):
    monkeypatch.setattr(
        main.tsetmc,
        "get_daily_prices",
        lambda code, count: [
            {"date": 20261112, "closing_price": 100},
            {"date": 20261113, "closing_price": 110},
            {"date": 20261114, "closing_price": 0},
            {"date": 20261115, "closing_price": -50},
            {"date": 20261116, "closing_price": "invalid"},
            {"date": 20261117, "closing_price": float("nan")},
        ],
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/analysis"
    )

    assert response.status_code == 200
    assert response.json["count"] == 2
    assert response.json["latest_date"] == 20261113


def test_stock_analysis_returns_ema_and_macd(monkeypatch):
    monkeypatch.setattr(
        main.tsetmc,
        "get_daily_prices",
        lambda code, count: [
            {"date": int((date(2026, 1, 1) + timedelta(days=i)).strftime("%Y%m%d")), "closing_price": 100 + i}
            for i in range(60)
        ],
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/analysis"
    )

    assert response.status_code == 200
    indicators = response.json["indicators"]

    assert indicators["ema"]["12"] is not None
    assert indicators["ema"]["26"] is not None
    assert indicators["macd"]["line"] is not None
    assert indicators["macd"]["signal"] is not None
    assert indicators["macd"]["histogram"] is not None


@pytest.mark.parametrize(
    ("url", "method", "args"),
    [
        ("/api/v1/stocks/search?q=فولاد", "search_instruments", ("فولاد",)),
        ("/api/v1/stocks/123456789", "get_instrument_info", ("123456789",)),
        ("/api/v1/stocks/123456789/prices", "get_closing_price_info", ("123456789",)),
        ("/api/v1/stocks/123456789/history", "get_daily_prices", ("123456789", 30)),
        ("/api/v1/stocks/123456789/analysis", "get_daily_prices", ("123456789", 365)),
    ],
)
def test_endpoints_handle_provider_schema_error(monkeypatch, url, method, args):
    from app.errors import ProviderSchemaError
    import pytest

    def fail(*_args):
        raise ProviderSchemaError("Invalid TSETMC response")

    monkeypatch.setattr(main.tsetmc, method, fail)

    response = main.app.test_client().get(url)

    assert response.status_code == 502
    assert response.json == {"detail": "Invalid TSETMC response"}


def test_stock_analysis_exposes_four_layers_without_fabricating_data(monkeypatch):
    monkeypatch.setattr(
        main.tsetmc,
        "get_daily_prices",
        lambda code, count: [
            {"date": 20261113, "closing_price": 100},
            {"date": 20261114, "closing_price": 110},
        ],
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/analysis"
    )

    assert response.status_code == 200
    body = response.json

    assert body["analysis_status"] == "PARTIAL"
    assert body["recommendation"]["action"] == "INSUFFICIENT_DATA"

    layers = body["layers"]
    assert layers["stock"]["technical"]["status"] == "AVAILABLE"
    assert layers["stock"]["fundamental"]["status"] == "UNAVAILABLE"
    assert layers["iran_economy"]["status"] == "UNAVAILABLE"
    assert layers["geopolitical"]["status"] == "UNAVAILABLE"
    assert layers["global_markets"]["status"] == "UNAVAILABLE"
