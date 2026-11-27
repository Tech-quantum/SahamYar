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
    assert response.json["analysis_status"] == "INSUFFICIENT_DATA"
    assert response.json["count"] == 2
    assert response.json["layers"]["stock"]["technical"]["status"] == "INSUFFICIENT_DATA"


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
    assert response.json["detail"] == "Upstream provider returned an invalid response."


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
    assert response.json == {"detail": "Upstream provider returned an invalid response."}


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

    assert body["analysis_status"] == "INSUFFICIENT_DATA"
    assert body["recommendation"]["action"] == "INSUFFICIENT_DATA"

    layers = body["layers"]
    assert layers["stock"]["status"] == "INSUFFICIENT_DATA"
    assert layers["stock"]["technical"]["status"] == "INSUFFICIENT_DATA"
    assert layers["stock"]["fundamental"]["status"] == "UNAVAILABLE"
    assert layers["iran_economy"]["status"] == "UNAVAILABLE"
    assert layers["geopolitical"]["status"] == "UNAVAILABLE"
    assert layers["global_markets"]["status"] == "UNAVAILABLE"


def _advanced_analysis_history(count=30):
    records = []
    start = date(2026, 10, 1)

    for index in range(count):
        close = 100 + index
        records.append({
            "date": int((start + timedelta(days=index)).strftime("%Y%m%d")),
            "closing_price": close,
            "max_price": close + 2,
            "min_price": close - 2,
            "volume": 100 + index * 10,
        })

    return records


def test_stock_analysis_returns_advanced_indicators(monkeypatch):
    monkeypatch.setattr(
        main.tsetmc,
        "get_daily_prices",
        lambda code, count: _advanced_analysis_history(),
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/analysis"
    )

    assert response.status_code == 200
    indicators = response.json["indicators"]
    advanced = indicators["advanced"]

    assert advanced["bollinger_bands"]["20"]["upper"] is not None
    assert advanced["bollinger_bands"]["20"]["middle"] is not None
    assert advanced["bollinger_bands"]["20"]["lower"] is not None
    assert advanced["atr"]["14"] is not None
    assert advanced["stochastic"]["14"]["k"] is not None
    assert advanced["stochastic"]["14"]["d"] is not None
    assert advanced["obv"] is not None
    assert advanced["volume_sma"]["20"] is not None
    assert advanced["volume_ratio"]["20"] is not None

    assert indicators["sma"]["20"] is not None
    assert indicators["ema"]["12"] is not None
    assert indicators["rsi"]["14"] is not None
    assert indicators["macd"]["line"] is not None


def test_stock_analysis_does_not_bridge_invalid_ohlc_candles(monkeypatch):
    history = _advanced_analysis_history()
    history[-1]["max_price"] = None

    monkeypatch.setattr(
        main.tsetmc,
        "get_daily_prices",
        lambda code, count: history,
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/analysis"
    )

    assert response.status_code == 200
    advanced = response.json["indicators"]["advanced"]

    assert advanced["atr"]["14"] is None
    assert advanced["stochastic"]["14"]["k"] is None
    assert advanced["stochastic"]["14"]["d"] is None

    assert advanced["bollinger_bands"]["20"]["middle"] is not None
    assert advanced["volume_sma"]["20"] is not None
    assert advanced["volume_ratio"]["20"] is not None
    assert advanced["obv"] is not None


def test_stock_analysis_keeps_ohlc_indicators_when_volume_is_invalid(monkeypatch):
    history = _advanced_analysis_history()
    history[-1]["volume"] = float("nan")

    monkeypatch.setattr(
        main.tsetmc,
        "get_daily_prices",
        lambda code, count: history,
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/analysis"
    )

    assert response.status_code == 200
    advanced = response.json["indicators"]["advanced"]

    assert advanced["atr"]["14"] is not None
    assert advanced["stochastic"]["14"]["k"] is not None
    assert advanced["stochastic"]["14"]["d"] is not None

    assert advanced["obv"] is None
    assert advanced["volume_sma"]["20"] is None
    assert advanced["volume_ratio"]["20"] is None



def test_stock_analysis_advanced_indicators_do_not_bridge_invalid_closes(monkeypatch):
    history = _advanced_analysis_history()
    history[-2]["closing_price"] = None

    monkeypatch.setattr(
        main.tsetmc,
        "get_daily_prices",
        lambda code, count: history,
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/analysis"
    )

    assert response.status_code == 200

    indicators = response.json["indicators"]
    advanced = indicators["advanced"]

    # Basic close-based indicators retain their existing filtering behavior.
    assert indicators["sma"]["20"] is not None

    # The invalid close breaks the contiguous history for advanced indicators.
    assert advanced["bollinger_bands"]["20"]["middle"] is None
    assert advanced["bollinger_bands"]["20"]["upper"] is None
    assert advanced["bollinger_bands"]["20"]["lower"] is None

    assert advanced["atr"]["14"] is None
    assert advanced["stochastic"]["14"]["k"] is None
    assert advanced["stochastic"]["14"]["d"] is None

    assert advanced["volume_sma"]["20"] is None
    assert advanced["volume_ratio"]["20"] is None

    # OBV restarts from the single valid candle after the broken observation.
    assert advanced["obv"] == 0


@pytest.mark.parametrize(
    ("url", "method"),
    [
        (
            "/api/v1/stocks/123456789/financial-reports",
            "search_reports",
        ),
        (
            "/api/v1/stocks/123456789/financial-reports/12345",
            "get_financial_report",
        ),
    ],
)
def test_codal_endpoints_sanitize_provider_errors(
    monkeypatch, caplog, url, method
):
    from app.errors import ProviderSchemaError

    secret_detail = "INTERNAL-CODAL-DETAIL-DO-NOT-EXPOSE"

    monkeypatch.setattr(
        main,
        "_codal_symbol_for_instrument",
        lambda code: "فولاد",
    )

    def fail(*args, **kwargs):
        raise ProviderSchemaError(secret_detail)

    monkeypatch.setattr(main.financial_service, method, fail)

    response = main.app.test_client().get(url)

    assert response.status_code == 502
    assert response.json["detail"] == (
        "Upstream provider returned an invalid response."
    )
    assert response.json["data_status"] == "unavailable"
    assert secret_detail not in response.get_data(as_text=True)
    assert secret_detail in caplog.text


def test_financial_report_not_found_does_not_expose_internal_error(
    monkeypatch,
):
    secret_detail = "INTERNAL-REPORT-LOOKUP-DETAIL-DO-NOT-EXPOSE"

    monkeypatch.setattr(
        main,
        "_codal_symbol_for_instrument",
        lambda code: "فولاد",
    )

    def fail(*args, **kwargs):
        raise LookupError(secret_detail)

    monkeypatch.setattr(
        main.financial_service,
        "get_financial_report",
        fail,
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/financial-reports/12345"
    )

    assert response.status_code == 404
    assert response.json["detail"] == (
        "The requested financial report was not found."
    )
    assert response.json["data_status"] == "not_found"
    assert secret_detail not in response.get_data(as_text=True)



def test_market_status_endpoint_returns_calendar_metadata():
    response = main.app.test_client().get("/api/v1/market/status")

    assert response.status_code == 200
    assert response.json["market"]["timezone"] == "Asia/Tehran"
    assert response.json["market"]["phase"] in {
        "pre_open", "continuous", "post_market", "closed"
    }
    assert response.json["calendar"]["available"] is True
    assert response.json["calendar"]["jalali_year"] == 1405
    assert response.json["calendar"]["source"]
    assert response.json["calendar"]["source_url"]
    assert isinstance(response.json["calendar"]["holidays"], list)
    assert isinstance(response.json["calendar"]["closure_events"], list)
    assert isinstance(response.json["calendar"]["warnings"], list)
    assert response.json["retrieved_at"]


def test_market_status_without_calendar_is_unknown_and_fail_closed(monkeypatch):
    monkeypatch.setattr(
        main,
        "market_hours",
        main.MarketHours(require_calendar=True),
    )

    response = main.app.test_client().get("/api/v1/market/status")

    assert response.status_code == 200
    assert response.json["market"]["status"] == "unknown"
    assert response.json["market"]["phase"] == "closed"
    assert response.json["market"]["is_trading_day"] is False
    assert response.json["market"]["trading_day_status"] == "unknown"
    assert response.json["calendar"]["available"] is False
    assert response.json["calendar"]["status"] == "needs_update"
    assert response.json["calendar"]["holidays"] == []


def test_market_status_only_exposes_global_closure_events(monkeypatch):
    from datetime import datetime
    from pathlib import Path
    from app.market_calendar import CalendarEvent, MarketCalendar, MarketScope

    now = datetime.now(main.TEHRAN)
    today = now.date()

    def event(event_id, level, status, symbol=None):
        return CalendarEvent(
            event_id=event_id,
            title=event_id,
            issuer="Test issuer",
            source_url="https://example.com/notice",
            published_at=now,
            effective_from=today,
            effective_to=today,
            scope=MarketScope(level=level, symbol=symbol),
            status=status,
        )

    events = [
        event("global-closure", "all_market", "confirmed"),
        event("global-warning", "all_market", "unverified"),
        event("symbol-closure", "symbol", "confirmed", "فولاد"),
    ]

    calendar_path = (
        Path(main.__file__).resolve().parent
        / "data" / "calendars" / "1405.json"
    )
    calendar = MarketCalendar.from_json(calendar_path, events=events)

    monkeypatch.setattr(
        main,
        "market_hours",
        main.MarketHours(calendar=calendar, require_calendar=True),
    )

    response = main.app.test_client().get("/api/v1/market/status")

    assert response.status_code == 200
    assert response.json["calendar"]["status"] == "emergency_closure"

    closures = response.json["calendar"]["closure_events"]
    warnings = response.json["calendar"]["warnings"]

    assert [item["event_id"] for item in closures] == ["global-closure"]
    assert [item["event_id"] for item in warnings] == ["global-warning"]
    assert all(
        item["scope"]["level"] == "all_market"
        for item in closures + warnings
    )


def test_market_status_serializes_official_holiday_details(monkeypatch):
    from datetime import datetime, timezone
    from app.market_calendar import CalendarHoliday, MarketCalendar

    fixed = datetime(2026, 12, 23, 10, 0, tzinfo=main.TEHRAN)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz) if tz else fixed

    monkeypatch.setattr(main, "datetime", FrozenDateTime)

    holiday = CalendarHoliday(
        day=fixed.date(),
        name="ولادت حضرت امام علی",
        source="تقویم رسمی کشور",
        source_url="https://example.com/calendar",
    )
    calendar = MarketCalendar(
        holidays=[holiday],
        calendar_year=2026,
        jalali_year=1405,
        source="تقویم رسمی کشور",
        source_url="https://example.com/calendar",
        updated_at=fixed,
    )
    monkeypatch.setattr(
        main, "market_hours",
        main.MarketHours(calendar=calendar, require_calendar=True),
    )

    response = main.app.test_client().get("/api/v1/market/status")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["calendar"]["status"] == "official_holiday"
    assert payload["calendar"]["holidays"] == [{
        "date": "2026-12-23",
        "name": "ولادت حضرت امام علی",
        "source": "تقویم رسمی کشور",
        "source_url": "https://example.com/calendar",
    }]
    assert payload["market"]["is_trading_day"] is False


def test_market_status_serializes_confirmed_closure_event(monkeypatch):
    from datetime import datetime
    from app.market_calendar import CalendarEvent, MarketCalendar, MarketScope

    fixed = datetime(2026, 11, 25, 10, 0, tzinfo=main.TEHRAN)
    event = CalendarEvent(
        event_id="test-closure",
        title="تعطیلی اضطراری بازار",
        issuer="نهاد صادرکننده",
        source_url="https://example.com/notice",
        published_at=fixed,
        effective_from=fixed.date(),
        effective_to=fixed.date(),
        scope=MarketScope(level="all_market"),
        status="confirmed",
    )
    calendar = MarketCalendar(
        events=[event],
        calendar_year=2026,
        jalali_year=1405,
        source="تقویم آزمایشی",
        source_url="https://example.com/calendar",
        updated_at=fixed,
    )

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz) if tz else fixed

    monkeypatch.setattr(main, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        main, "market_hours",
        main.MarketHours(calendar=calendar, require_calendar=True),
    )

    response = main.app.test_client().get("/api/v1/market/status")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["calendar"]["status"] == "emergency_closure"
    assert payload["calendar"]["closure_events"] == [{
        "event_id": "test-closure",
        "title": "تعطیلی اضطراری بازار",
        "issuer": "نهاد صادرکننده",
        "source_url": "https://example.com/notice",
        "published_at": fixed.isoformat(),
        "effective_from": fixed.date().isoformat(),
        "effective_to": fixed.date().isoformat(),
        "scope": {
            "level": "all_market",
            "market": None,
            "symbol": None,
            "operation": None,
        },
        "status": "confirmed",
        "expires_at": None,
    }]
    assert payload["market"]["is_trading_day"] is False


def test_market_status_unverified_notice_is_warning_not_closure(monkeypatch):
    from datetime import datetime
    from app.market_calendar import CalendarEvent, MarketCalendar, MarketScope

    fixed = datetime(2026, 11, 25, 10, 0, tzinfo=main.TEHRAN)
    event = CalendarEvent(
        event_id="test-warning",
        title="خبر تأییدنشده درباره تعطیلی",
        issuer="منبع غیررسمی",
        source_url="https://example.com/unverified",
        published_at=fixed,
        effective_from=fixed.date(),
        effective_to=fixed.date(),
        scope=MarketScope(level="all_market"),
        status="unverified",
    )
    calendar = MarketCalendar(
        events=[event],
        calendar_year=2026,
        jalali_year=1405,
        source="تقویم آزمایشی",
        source_url="https://example.com/calendar",
        updated_at=fixed,
    )

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz) if tz else fixed

    monkeypatch.setattr(main, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        main, "market_hours",
        main.MarketHours(calendar=calendar, require_calendar=True),
    )

    response = main.app.test_client().get("/api/v1/market/status")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["calendar"]["status"] == "open_with_unverified_notice"
    assert payload["calendar"]["closure_events"] == []
    assert len(payload["calendar"]["warnings"]) == 1
    assert payload["calendar"]["warnings"][0]["event_id"] == "test-warning"
    assert payload["calendar"]["warnings"][0]["status"] == "unverified"
    assert payload["market"]["is_trading_day"] is True
    assert payload["market"]["phase"] == "continuous"
    assert payload["market"]["status"] == "open"

def test_market_status_returns_full_annual_holiday_list(monkeypatch):
    from datetime import datetime
    from app.market_calendar import CalendarHoliday, MarketCalendar

    fixed = datetime(2026, 12, 23, 10, 0, tzinfo=main.TEHRAN)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz) if tz else fixed

    holidays = [
        CalendarHoliday(
            day=fixed.date().replace(day=24),
            name="تعطیلی دوم",
            source="تقویم رسمی",
            source_url="https://example.com/calendar",
        ),
        CalendarHoliday(
            day=fixed.date(),
            name="تعطیلی امروز",
            source="تقویم رسمی",
            source_url="https://example.com/calendar",
        ),
    ]
    calendar = MarketCalendar(
        holidays=holidays,
        calendar_year=2026,
        jalali_year=1405,
        source="تقویم رسمی",
        source_url="https://example.com/calendar",
        updated_at=fixed,
    )

    monkeypatch.setattr(main, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        main,
        "market_hours",
        main.MarketHours(calendar=calendar, require_calendar=True),
    )

    response = main.app.test_client().get("/api/v1/market/status")
    payload = response.get_json()

    assert response.status_code == 200
    assert [item["date"] for item in payload["calendar"]["holidays"]] == [
        "2026-12-23",
        "2026-12-24",
    ]
    assert [item["date"] for item in payload["calendar"]["today_holidays"]] == [
        "2026-12-23",
    ]


@pytest.mark.parametrize(
    ("url", "method"),
    [
        ("/api/v1/stocks/search?q=فولاد", "search_instruments"),
        ("/api/v1/stocks/123456789", "get_instrument_info"),
        ("/api/v1/stocks/123456789/prices", "get_closing_price_info"),
        ("/api/v1/stocks/123456789/history", "get_daily_prices"),
        ("/api/v1/stocks/123456789/analysis", "get_daily_prices"),
    ],
)
def test_tsetmc_endpoints_sanitize_provider_errors(
    monkeypatch, caplog, url, method
):
    secret_detail = "INTERNAL-TSETMC-DETAIL-DO-NOT-EXPOSE"

    def fail(*args, **kwargs):
        raise ProviderUnavailable(secret_detail)

    monkeypatch.setattr(main.tsetmc, method, fail)

    response = main.app.test_client().get(url)

    assert response.status_code == 502
    assert response.json == {
        "detail": "Upstream data provider is temporarily unavailable."
    }
    assert secret_detail not in response.get_data(as_text=True)
    assert secret_detail in caplog.text


def test_market_scoped_status_filters_events(monkeypatch):
    from datetime import datetime
    from app.market_calendar import CalendarEvent, MarketCalendar, MarketScope

    fixed = datetime(2026, 11, 25, 10, 0, tzinfo=main.TEHRAN)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz) if tz else fixed

    def event(event_id, scope):
        return CalendarEvent(
            event_id=event_id,
            title=event_id,
            issuer="Official authority",
            source_url="https://example.com/notice",
            published_at=fixed,
            effective_from=fixed.date(),
            effective_to=fixed.date(),
            scope=scope,
            status="confirmed",
        )

    calendar = MarketCalendar(
        events=[
            event("global", MarketScope(level="all_market")),
            event("target-market", MarketScope(
                level="market", market="stock_exchange"
            )),
            event("other-market", MarketScope(
                level="market", market="commodity_exchange"
            )),
            event("symbol-only", MarketScope(
                level="symbol", symbol="فولاد"
            )),
        ],
        calendar_year=2026,
        jalali_year=1405,
        source="Test calendar",
        source_url="https://example.com/calendar",
        updated_at=fixed,
    )

    monkeypatch.setattr(main, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        main,
        "market_hours",
        main.MarketHours(calendar=calendar, require_calendar=True),
    )

    response = main.app.test_client().get(
        "/api/v1/markets/stock_exchange/status"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["scope"]["level"] == "market"
    assert payload["scope"]["market"] == "stock_exchange"
    assert {
        item["event_id"] for item in payload["calendar"]["closure_events"]
    } == {"global", "target-market"}


def test_stock_market_status_includes_matching_scoped_events(monkeypatch):
    from datetime import datetime
    from app.market_calendar import CalendarEvent, MarketCalendar, MarketScope

    fixed = datetime(2026, 11, 25, 10, 0, tzinfo=main.TEHRAN)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz) if tz else fixed

    def event(event_id, scope):
        return CalendarEvent(
            event_id=event_id,
            title=event_id,
            issuer="Official authority",
            source_url="https://example.com/notice",
            published_at=fixed,
            effective_from=fixed.date(),
            effective_to=fixed.date(),
            scope=scope,
            status="confirmed",
        )

    calendar = MarketCalendar(
        events=[
            event("global", MarketScope(level="all_market")),
            event("market", MarketScope(
                level="market", market="stock_exchange"
            )),
            event("matching-symbol", MarketScope(
                level="symbol",
                market="stock_exchange",
                symbol="فولاد",
            )),
            event("wrong-market-symbol", MarketScope(
                level="symbol",
                market="commodity_exchange",
                symbol="فولاد",
            )),
            event("other-symbol", MarketScope(
                level="symbol",
                market="stock_exchange",
                symbol="فملی",
            )),
        ],
        calendar_year=2026,
        jalali_year=1405,
        source="Test calendar",
        source_url="https://example.com/calendar",
        updated_at=fixed,
    )

    monkeypatch.setattr(main, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        main,
        "market_hours",
        main.MarketHours(calendar=calendar, require_calendar=True),
    )
    monkeypatch.setattr(
        main.tsetmc,
        "get_instrument_info",
        lambda code: {
            "ins_code": code,
            "symbol": "فولاد",
            "market": "stock_exchange",
            "instrument_category": "COMMON_STOCK",
        },
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/market-status"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["scope"]["symbol"] == "فولاد"
    assert {
        item["event_id"] for item in payload["calendar"]["closure_events"]
    } == {"global", "market", "matching-symbol"}


def test_scoped_market_status_without_calendar_is_unknown_and_fail_closed(
    monkeypatch,
):
    monkeypatch.setattr(
        main,
        "market_hours",
        main.MarketHours(require_calendar=True),
    )

    response = main.app.test_client().get(
        "/api/v1/markets/stock_exchange/status"
    )

    assert response.status_code == 200
    calendar = response.json["calendar"]
    assert calendar["available"] is False
    assert calendar["status"] == "unknown"
    assert calendar["is_closed"] is None
    assert calendar["calendar_status"] == "needs_update"
    assert calendar["closure_events"] == []
    assert calendar["warnings"] == []


@pytest.mark.parametrize(
    "instrument",
    [
        None,
        {},
        {"symbol": "فولاد"},
        {"market": "stock_exchange"},
        {"symbol": " ", "market": "stock_exchange"},
        {"symbol": "فولاد", "market": ""},
    ],
)
def test_stock_market_status_rejects_incomplete_instrument_metadata(
    monkeypatch, instrument
):
    monkeypatch.setattr(
        main.tsetmc,
        "get_instrument_info",
        lambda code: instrument,
    )

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/market-status"
    )

    assert response.status_code == 502
    assert response.json == {
        "detail": "Upstream provider returned an invalid response."
    }


@pytest.mark.parametrize(
    "error_type",
    [
        pytest.param(
            __import__("app.errors", fromlist=["ProviderUnavailable"]).ProviderUnavailable,
            id="provider-unavailable",
        ),
        pytest.param(
            __import__("app.errors", fromlist=["ProviderSchemaError"]).ProviderSchemaError,
            id="provider-schema-error",
        ),
    ],
)
def test_stock_market_status_sanitizes_provider_errors(
    monkeypatch, error_type
):
    secret_detail = "INTERNAL-TSETMC-DETAIL-DO-NOT-EXPOSE"

    def fail(code):
        raise error_type(secret_detail)

    monkeypatch.setattr(main.tsetmc, "get_instrument_info", fail)

    response = main.app.test_client().get(
        "/api/v1/stocks/123456789/market-status"
    )

    assert response.status_code == 502
    assert secret_detail not in response.get_data(as_text=True)
    assert response.json["detail"] in {
        "Upstream provider returned an invalid response.",
        "Upstream data provider is temporarily unavailable.",
    }


def test_stock_market_status_rejects_invalid_instrument_code():
    response = main.app.test_client().get(
        "/api/v1/stocks/abc/market-status"
    )

    assert response.status_code == 400


def test_scoped_market_status_rejects_oversized_market_identifier():
    market = "x" * 129

    response = main.app.test_client().get(
        f"/api/v1/markets/{market}/status"
    )

    assert response.status_code == 400
