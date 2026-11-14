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
