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
