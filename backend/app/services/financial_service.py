"""Application service connecting Codal report discovery and parsing."""

from decimal import Decimal
from typing import Any

from app.errors import ProviderSchemaError
from app.providers.codal import (
    parse_statement_html,
    standardize_financial_report,
)
from app.providers.codal_client import CodalClient


def _json_safe(value: Any) -> Any:
    """Preserve exact financial values by encoding Decimal as strings."""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


class CodalFinancialService:
    """Fetch reports through Codal search results, never arbitrary URLs."""

    def __init__(self, client: CodalClient) -> None:
        self.client = client

    def search_reports(self, symbol: str, page: int = 1) -> dict[str, Any]:
        result = self.client.search_letters(symbol, page=page)
        items = []

        for letter in result["letters"]:
            item = {
                key: letter.get(key)
                for key in (
                    "tracing_no",
                    "symbol",
                    "company_name",
                    "title",
                    "letter_code",
                    "sent_at",
                    "published_at",
                    "has_html",
                    "has_excel",
                    "has_pdf",
                )
            }

            raw_url = letter.get("url")
            if raw_url:
                try:
                    item["report_url"] = self.client.resolve_report_url(raw_url)
                except ValueError:
                    item["report_url"] = None
            else:
                item["report_url"] = None

            items.append(item)

        return {
            "source": "CODAL",
            "symbol": symbol,
            "page": result.get("page") or page,
            "total": result.get("total"),
            "count": len(items),
            "items": items,
        }

    def get_financial_report(
        self,
        symbol: str,
        tracing_no: str,
        page: int = 1,
    ) -> dict[str, Any]:
        if not isinstance(tracing_no, str) or not tracing_no.isdigit():
            raise ValueError("tracing_no must contain digits only.")

        result = self.client.search_letters(symbol, page=page)

        letter = next(
            (
                item
                for item in result["letters"]
                if str(item.get("tracing_no")) == tracing_no
            ),
            None,
        )

        if letter is None:
            raise LookupError(
                "The requested report was not found on this Codal page."
            )

        if not letter.get("has_html") or not letter.get("url"):
            raise ProviderSchemaError(
                "The selected Codal report does not provide an HTML statement."
            )

        try:
            safe_url = self.client.resolve_report_url(letter["url"])
        except ValueError as exc:
            raise ProviderSchemaError(
                "Codal returned an unsafe report URL."
            ) from exc

        document = self.client.get_report_html(safe_url)

        try:
            parsed = parse_statement_html(document)
            standardized = standardize_financial_report(parsed)
        except (TypeError, ValueError, KeyError) as exc:
            raise ProviderSchemaError(
                "Codal report could not be parsed."
            ) from exc

        return _json_safe({
            "source": "CODAL",
            "symbol": symbol,
            "tracing_no": tracing_no,
            "title": letter.get("title"),
            "letter_code": letter.get("letter_code"),
            "published_at": letter.get("published_at"),
            "sent_at": letter.get("sent_at"),
            "report_url": safe_url,
            "data_status": "available",
            "report": standardized,
        })
