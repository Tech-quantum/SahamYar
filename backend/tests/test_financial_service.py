import pytest

from app.errors import ProviderSchemaError
from app.services.financial_service import CodalFinancialService


def test_search_reports_sanitizes_provider_rows_and_urls():
    class FakeClient:
        def search_letters(self, symbol, page=1):
            assert (symbol, page) == ("فولاد", 2)
            return {
                "total": 12,
                "page": 2,
                "letters": [
                    {
                        "tracing_no": 123,
                        "symbol": "فولاد",
                        "title": "صورت مالی",
                        "has_html": True,
                        "url": "/Reports/Decision.aspx?id=1",
                        "raw": {"internal": "not exposed"},
                    },
                    {
                        "tracing_no": 124,
                        "has_html": True,
                        "url": "https://evil.example/x",
                        "raw": {},
                    },
                ],
            }

        @staticmethod
        def resolve_report_url(url):
            if url.startswith("https://evil"):
                raise ValueError("unsafe")
            return "https://codal.ir" + url

    result = CodalFinancialService(FakeClient()).search_reports("فولاد", 2)

    assert result["source"] == "CODAL"
    assert result["count"] == 2
    assert result["items"][0]["report_url"].startswith("https://codal.ir/")
    assert result["items"][1]["report_url"] is None
    assert "raw" not in result["items"][0]


def test_get_financial_report_rejects_non_numeric_tracing_number():
    with pytest.raises(ValueError):
        CodalFinancialService(object()).get_financial_report("فولاد", "../")


def test_get_financial_report_never_fetches_unlisted_report():
    class FakeClient:
        def search_letters(self, symbol, page=1):
            return {"letters": []}

    with pytest.raises(LookupError):
        CodalFinancialService(FakeClient()).get_financial_report("فولاد", "123")


def test_get_financial_report_requires_html_statement():
    class FakeClient:
        def search_letters(self, symbol, page=1):
            return {
                "letters": [{
                    "tracing_no": 123,
                    "has_html": False,
                    "url": "/Reports/Decision.aspx?id=1",
                }]
            }

        @staticmethod
        def resolve_report_url(url):
            return "https://codal.ir" + url

    with pytest.raises(ProviderSchemaError):
        CodalFinancialService(FakeClient()).get_financial_report("فولاد", "123")


def test_financial_report_routes_registered():
    from app import main

    routes = {rule.rule for rule in main.app.url_map.iter_rules()}

    assert "/api/v1/stocks/<ins_code>/financial-reports" in routes
    assert (
        "/api/v1/stocks/<ins_code>/financial-reports/<tracing_no>"
        in routes
    )


def test_financial_report_parser_error_does_not_expose_internal_details(
    monkeypatch,
):
    class FakeClient:
        def search_letters(self, symbol, page=1):
            return {
                "letters": [{
                    "tracing_no": 123,
                    "has_html": True,
                    "url": "/Reports/Decision.aspx?id=1",
                }]
            }

        @staticmethod
        def resolve_report_url(url):
            return "https://codal.ir" + url

        @staticmethod
        def get_report_html(url):
            return "<html>test</html>"

    internal_detail = "INTERNAL-PARSER-DETAIL-DO-NOT-EXPOSE"

    def fail_parser(document):
        raise ValueError(internal_detail)

    monkeypatch.setattr(
        "app.services.financial_service.parse_statement_html",
        fail_parser,
    )

    service = CodalFinancialService(FakeClient())
    with pytest.raises(ProviderSchemaError) as error:
        service.get_financial_report("فولاد", "123")

    assert str(error.value) == "Codal report could not be parsed."
    assert internal_detail not in str(error.value)
    assert internal_detail in str(error.value.__cause__)
