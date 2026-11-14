import httpx
import pytest

from app.errors import ProviderSchemaError
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
                "sector": {"lSecVal": "فلزات اساسی"},
                "eps": {"estimatedEPS": "693", "sectorPE": 11.34},
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
    assert result["eps"]["estimatedEPS"] == "693"
    assert result["raw"]["future_field"] == "preserved"


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
        assert "ClosingPrice/GetClosingPriceDailyList/123456789/5" in str(request.url)
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
