import app.main as main
from app.errors import ProviderUnavailable


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
        },
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789"
    )

    assert response.status_code == 200
    assert response.json["source"] == "TSETMC"
    assert response.json["item"]["symbol"] == "فولاد"


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


def test_stock_prices_rejects_invalid_code():
    response = main.app.test_client().get(
        "/api/v1/stocks/abc/prices"
    )
    assert response.status_code == 400


def test_stock_prices_handles_provider_error(monkeypatch):
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
