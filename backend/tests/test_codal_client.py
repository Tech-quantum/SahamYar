import httpx
import pytest

from app.errors import ProviderSchemaError, ProviderUnavailable
from app.providers.codal_client import CodalClient


def make_client(handler, max_retries=0):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return CodalClient(http_client=http, min_interval=0, max_retries=max_retries), http


def test_get_companies_normalizes_and_preserves_raw():
    def handler(request):
        assert request.url.path == "/api/search/v1/companies"
        return httpx.Response(200, json=[
            {"sy": " فولاد ", "n": "فولاد مبارکه", "i": "811620", "extra": 1},
            {"sy": "", "n": "بدون نماد"},
            "not-a-dict",
        ])

    client, http = make_client(handler)
    result = client.get_companies()
    http.close()

    assert len(result) == 1
    assert result[0]["symbol"] == "فولاد"
    assert result[0]["name"] == "فولاد مبارکه"
    assert result[0]["codal_id"] == "811620"
    assert result[0]["raw"]["extra"] == 1


def test_get_companies_rejects_non_list_root():
    client, http = make_client(lambda request: httpx.Response(200, json={"a": 1}))
    with pytest.raises(ProviderSchemaError):
        client.get_companies()
    http.close()


def test_search_letters_sends_params_and_normalizes():
    seen = {}

    def handler(request):
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={
            "Total": 688,
            "Page": 35,
            "Letters": [{
                "TracingNo": 123,
                "Symbol": "فولاد",
                "CompanyName": "فولاد مبارکه",
                "Title": "صورت‌های مالی میان‌دوره‌ای",
                "LetterCode": "ن-۱۰",
                "SentDateTime": "1405/06/31 10:00:00",
                "PublishDateTime": "1405/06/31 10:05:00",
                "HasHtml": True,
                "HasExcel": True,
                "HasPdf": False,
                "Url": "/Reports/Decision.aspx?LetterSerial=abc",
                "Unknown": "kept",
            }],
            "IsAttacker": False,
        })

    client, http = make_client(handler)
    result = client.search_letters("فولاد", page=2)
    http.close()

    assert seen["Symbol"] == "فولاد"
    assert seen["PageNumber"] == "2"
    assert result["total"] == 688
    assert result["page"] == 35
    letter = result["letters"][0]
    assert letter["tracing_no"] == 123
    assert letter["has_html"] is True
    assert letter["has_pdf"] is False
    assert letter["url"] == "/Reports/Decision.aspx?LetterSerial=abc"
    assert letter["raw"]["Unknown"] == "kept"


def test_search_letters_rejects_bad_input_and_bad_schema():
    client, http = make_client(lambda request: httpx.Response(200, json={"Total": 1}))
    with pytest.raises(ValueError):
        client.search_letters("  ")
    with pytest.raises(ValueError):
        client.search_letters("فولاد", page=0)
    with pytest.raises(ProviderSchemaError):
        client.search_letters("فولاد")
    http.close()


def test_resolve_report_url_accepts_relative_and_codal_hosts():
    resolve = CodalClient.resolve_report_url
    assert resolve("/Reports/Decision.aspx?LetterSerial=abc") == (
        "https://codal.ir/Reports/Decision.aspx?LetterSerial=abc"
    )
    assert resolve("https://search.codal.ir/x") == "https://search.codal.ir/x"


@pytest.mark.parametrize("bad_url", [
    "http://codal.ir/x",
    "https://evil.example.com/x",
    "https://codal.ir.evil.com/x",
    "https://user:pass@codal.ir/x",
    "//evil.example.com/x",
    "",
])
def test_resolve_report_url_rejects_unsafe_urls(bad_url):
    with pytest.raises(ValueError):
        CodalClient.resolve_report_url(bad_url)


def test_retry_then_success(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=[])

    client, http = make_client(handler, max_retries=1)
    assert client.get_companies() == []
    assert calls["n"] == 2
    http.close()


def test_provider_unavailable_after_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    client, http = make_client(lambda request: httpx.Response(503), max_retries=1)
    with pytest.raises(ProviderUnavailable):
        client.get_companies()
    http.close()


def test_non_json_response_raises_schema_error():
    client, http = make_client(lambda request: httpx.Response(200, text="<html>"))
    with pytest.raises(ProviderSchemaError):
        client.get_companies()
    http.close()


def test_get_report_html_returns_text_and_rejects_empty():
    def handler(request):
        if request.url.path == "/empty":
            return httpx.Response(200, text="   ")
        return httpx.Response(200, text="<html>report</html>")

    client, http = make_client(handler)
    assert client.get_report_html("/ok") == "<html>report</html>"
    with pytest.raises(ProviderSchemaError):
        client.get_report_html("/empty")
    http.close()


def test_get_report_html_rejects_foreign_host_without_request():
    def handler(request):
        raise AssertionError("no request should be made")

    client, http = make_client(handler)
    with pytest.raises(ValueError):
        client.get_report_html("https://evil.example.com/x")
    http.close()


def test_invalid_constructor_arguments():
    with pytest.raises(ValueError):
        CodalClient(min_interval=-1)
    with pytest.raises(ValueError):
        CodalClient(max_retries=-1)
    with pytest.raises(ValueError):
        CodalClient(timeout=0)
