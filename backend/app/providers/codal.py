"""Offline parser for Codal financial-statement HTML."""

from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import re
from typing import Any


STATEMENT_NAMES = (
    "income_statement",
    "comprehensive_income",
    "balance_sheet",
    "equity_changes",
    "cash_flow",
)

PERSIAN_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def normalize_text(value: str) -> str:
    """Normalize whitespace and Persian/Arabic digits without changing meaning."""
    value = value.translate(PERSIAN_DIGITS)
    value = value.replace("\u200c", " ").replace("\u200f", "")
    value = value.replace("\u200e", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def parse_financial_number(value: str) -> Decimal | None:
    """Parse financial values exactly; preserve blanks and reject invalid data."""
    text = normalize_text(value)
    if not text or text in {"-", "—", "–"}:
        return None

    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()

    text = (
        text.replace(",", "")
        .replace("٬", "")
        .replace("٫", ".")
        .replace("%", "")
        .replace("−", "-")
        .replace("٪", "")
        .strip()
    )

    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return None

    if not number.is_finite():
        return None
    return -abs(number) if negative else number


class _FirstTableParser(HTMLParser):
    """Extract the first table and its direct rows/cells."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.table_depth = 0
        self.found_table = False
        self.finished = False
        self.rows: list[list[dict[str, Any]]] = []
        self.current_row: list[dict[str, Any]] | None = None
        self.current_cell: dict[str, Any] | None = None
        self.cell_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)

        if tag == "table":
            if not self.found_table:
                self.found_table = True
                self.table_depth = 1
            elif self.table_depth:
                self.table_depth += 1
            return

        if not self.table_depth or self.finished:
            return

        if tag == "tr" and self.table_depth == 1:
            self.current_row = []
        elif tag in ("td", "th") and self.table_depth == 1:
            self.current_cell = {
                "tag": tag,
                "classes": (attributes.get("class") or "").split(),
                "rowspan": attributes.get("rowspan", "1"),
                "colspan": attributes.get("colspan", "1"),
                "text": "",
            }
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        if self.current_cell is not None and self.table_depth == 1:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self.current_cell is not None:
            raw_text = "".join(self.cell_parts)
            self.current_cell["text"] = raw_text
            self.current_cell["normalized_text"] = normalize_text(raw_text)
            if self.current_row is not None:
                self.current_row.append(self.current_cell)
            self.current_cell = None
            self.cell_parts = []
        elif tag == "tr" and self.current_row is not None:
            self.rows.append(self.current_row)
            self.current_row = None
        elif tag == "table" and self.table_depth:
            self.table_depth -= 1
            if self.table_depth == 0:
                self.finished = True


def _first_table(section_html: str) -> list[list[dict[str, Any]]]:
    parser = _FirstTableParser()
    parser.feed(section_html)
    parser.close()
    if not parser.found_table or not parser.rows:
        return []
    return parser.rows



def expand_table_rows(rows: list[list[dict[str, Any]]]) -> list[list[dict[str, Any]]]:
    """Expand HTML spans while marking cells copied from merged cells."""
    expanded = []
    active: dict[int, tuple[dict[str, Any], int]] = {}

    for source_row in rows:
        row: list[dict[str, Any] | None] = []

        for column, (cell, remaining) in list(active.items()):
            while len(row) <= column:
                row.append(None)
            copied = dict(cell)
            copied["span_origin"] = True
            row[column] = copied
            if remaining <= 1:
                del active[column]
            else:
                active[column] = (cell, remaining - 1)

        column = 0
        for cell in source_row:
            while column < len(row) and row[column] is not None:
                column += 1

            try:
                colspan = max(1, int(cell.get("colspan", 1)))
                rowspan = max(1, int(cell.get("rowspan", 1)))
            except (TypeError, ValueError):
                colspan = rowspan = 1

            for offset in range(colspan):
                target = column + offset
                while len(row) <= target:
                    row.append(None)

                placed = dict(cell)
                if offset:
                    placed["span_origin"] = True
                row[target] = placed

                if rowspan > 1:
                    active[target] = (cell, rowspan - 1)

            column += colspan

        expanded.append([
            cell if cell is not None else {
                "tag": "td",
                "classes": [],
                "rowspan": "1",
                "colspan": "1",
                "text": "",
                "normalized_text": "",
                "span_origin": True,
            }
            for cell in row
        ])

    width = max((len(row) for row in expanded), default=0)
    for row in expanded:
        while len(row) < width:
            row.append({
                "tag": "td",
                "classes": [],
                "rowspan": "1",
                "colspan": "1",
                "text": "",
                "normalized_text": "",
                "span_origin": True,
            })

    return expanded


def _detect_report_unit(document: str) -> str | None:
    """Return a unit only when it is explicitly stated in the report."""
    from html import unescape

    text = normalize_text(unescape(re.sub(r"<[^>]+>", " ", document)))
    if "کلیه مبالغ درج شده به میلیون ریال می باشد" in text:
        return "million_rial"
    return None


def parse_statement_html(document: str) -> dict[str, Any]:
    """Parse the five primary statements from a Codal Excel HTML document."""
    if not isinstance(document, str) or not document.strip():
        raise ValueError("Codal HTML document must be a non-empty string.")

    starts = list(re.finditer(r"<app-statement\b", document, re.I))
    if len(starts) < 5:
        raise ValueError("Codal document does not contain five statement sections.")

    result: dict[str, Any] = {}
    for index, name in enumerate(STATEMENT_NAMES):
        start = starts[index].start()
        end = starts[index + 1].start() if index + 1 < len(starts) else len(document)
        rows = _first_table(document[start:end])
        if not rows:
            raise ValueError(f"Primary statement table is missing: {name}")
        result[name] = {
            "rows": rows,
            "row_count": len(rows),
            "column_count": max((len(row) for row in rows), default=0),
        }

    parsed_statements = {}
    for name, statement in result.items():
        logical_rows = expand_table_rows(statement["rows"])
        parsed_statement = {
            **statement,
            "logical_rows": logical_rows,
        }
        parsed_statement["column_metadata"] = extract_statement_columns(
            name, parsed_statement
        )
        parsed_statements[name] = parsed_statement

    return {
        "source": "Codal",
        "parser_version": 1,
        "unit": _detect_report_unit(document),
        "statements": parsed_statements,
    }




def normalize_label(value: str) -> str:
    """Normalize Persian and Arabic financial labels for matching."""
    text = normalize_text(value)
    text = text.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک")
    text = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text)
    text = re.sub(r"[()\[\]{}،؛:,.٪%]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classify_equity_event(label: str) -> dict[str, str | None]:
    """Classify equity-change rows by label, never by row position."""
    normalized = normalize_label(label)
    event_type = "unknown"

    if "مانده" in normalized and "تجدید ارائه" in normalized:
        event_type = "restated_balance"
    elif "مانده" in normalized:
        event_type = "balance_snapshot"
    else:
        rules = (
            ("سود زیان خالص تجدید ارائه شده", "restated_net_profit"),
            ("سود زیان خالص گزارش شده", "reported_net_profit"),
            ("سود زیان خالص در دوره", "current_period_profit"),
            ("سایر اقلام سود و زیان جامع", "other_comprehensive_income"),
            ("سود زیان جامع", "comprehensive_income"),
            ("سود سهام مصوب", "dividend"),
            ("اصلاح اشتباهات", "correction"),
            ("تغییر در رویه های حسابداری", "accounting_policy_change"),
            ("افزایش سرمایه در جریان", "capital_increase_in_progress"),
            ("افزایش سرمایه", "capital_increase"),
            ("خرید سهام خزانه", "treasury_share_purchase"),
            ("فروش سهام خزانه", "treasury_share_sale"),
            ("تخصیص به سایر اندوخته", "reserve_allocation"),
            ("تخصیص به اندوخته", "reserve_allocation"),
            ("انتقال از", "equity_transfer"),
            ("انتقال به", "equity_transfer"),
        )
        for phrase, candidate in rules:
            if phrase in normalized:
                event_type = candidate
                break

    match = re.search(r"(?<!\d)(\d{4}/\d{1,2}/\d{1,2})(?!\d)", normalized)
    return {
        "event_type": event_type,
        "event_date": match.group(1) if match else None,
    }

def extract_statement_rows(statement: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert logical HTML rows into structured financial rows."""
    logical_rows = statement.get("logical_rows")
    if not isinstance(logical_rows, list):
        raise ValueError("Statement must contain logical_rows.")

    extracted = []

    for row_index, cells in enumerate(logical_rows):
        if not cells or cells[0].get("span_origin", False):
            continue

        label = cells[0].get("normalized_text", "").strip()
        if not label:
            continue

        values = [
            parse_financial_number(cell.get("normalized_text", ""))
            for cell in cells[1:]
        ]

        # Ignore headers and section headings without numeric data.
        if not any(value is not None for value in values):
            continue

        extracted_row = {
            "row_index": row_index,
            "label": label,
            "normalized_label": normalize_label(label),
            "values": values,
            "raw_values": [
                cell.get("text", "") for cell in cells[1:]
            ],
            "classes": list(cells[0].get("classes", [])),
            "is_calculated": any(
                "dynamic_comp" in cell.get("classes", [])
                for cell in cells
            ),
        }

        column_metadata = statement.get("column_metadata")
        if isinstance(column_metadata, dict):
            period_values = {}
            period_raw_values = {}

            for period in column_metadata.get("periods", []):
                column_index = period.get("column_index")
                role = period.get("role")

                if (
                    type(column_index) is not int
                    or column_index < 1
                    or not isinstance(role, str)
                ):
                    continue

                value_index = column_index - 1
                period_values[role] = (
                    values[value_index]
                    if value_index < len(values)
                    else None
                )
                period_raw_values[role] = (
                    cells[column_index].get("text", "")
                    if column_index < len(cells)
                    else ""
                )

            extracted_row["period_values"] = period_values
            extracted_row["period_raw_values"] = period_raw_values

            if column_metadata.get("statement_type") == "equity_changes":
                extracted_row.update(classify_equity_event(label))
                component_values = {}
                component_raw_values = {}

                for column in column_metadata.get("columns", []):
                    column_index = column.get("column_index")
                    component_name = column.get("normalized_label")

                    if (
                        type(column_index) is not int
                        or column_index < 1
                        or not isinstance(component_name, str)
                        or not component_name
                    ):
                        continue

                    value_index = column_index - 1
                    component_values[component_name] = (
                        values[value_index]
                        if value_index < len(values)
                        else None
                    )
                    component_raw_values[component_name] = (
                        cells[column_index].get("text", "")
                        if column_index < len(cells)
                        else ""
                    )

                extracted_row["equity_component_values"] = component_values
                extracted_row["equity_component_raw_values"] = component_raw_values

            extracted_row["change_percent"] = None
            extracted_row["change_percent_raw"] = ""

            change_column = column_metadata.get("change_column")
            if isinstance(change_column, dict):
                change_index = change_column.get("column_index")
                valid_change_index = (
                    type(change_index) is int and change_index >= 1
                )
                value_index = change_index - 1 if valid_change_index else -1

                extracted_row["change_percent_unit"] = (
                    "percent" if valid_change_index else "unknown"
                )
                extracted_row["change_percent"] = (
                    values[value_index]
                    if 0 <= value_index < len(values)
                    else None
                )
                extracted_row["change_percent_raw"] = (
                    cells[change_index].get("text", "")
                    if valid_change_index and change_index < len(cells)
                    else ""
                )

        extracted.append(extracted_row)

    return extracted


# Exact, statement-specific aliases. Unknown labels are never guessed.
STATEMENT_METRIC_ALIASES = {
    "income_statement": {
        "درآمدهای عملیاتی": "operating_revenue",
        "بهای تمام شده درآمدهای عملیاتی": "cost_of_revenue",
        "سود زیان ناخالص": "gross_profit",
        "هزینه های فروش اداری و عمومی": "selling_general_admin_expenses",
        "هزینه کاهش ارزش دریافتنی ها هزینه استثنایی": "receivables_impairment",
        "سایر درآمدها": "other_income",
        "سایر هزینه ها": "other_expenses",
        "سود زیان عملیاتی": "operating_profit",
        "هزینه های مالی": "finance_costs",
        "سایر درآمدها و هزینه های غیرعملیاتی": "non_operating_net",
        "سود زیان عملیات در حال تداوم قبل از مالیات": "profit_before_tax",
        "سال جاری": "income_tax_current",
        "سال های قبل": "income_tax_prior",
        "سود زیان خالص عملیات در حال تداوم": "continuing_operations_profit",
        "سود زیان خالص عملیات متوقف شده": "discontinued_operations_profit",
        "سود زیان خالص": "net_profit",
        "عملیاتی ریال": "eps_operating",
        "غیرعملیاتی ریال": "eps_non_operating",
        "ناشی از عملیات در حال تداوم": "eps_continuing_operations",
        "ناشی از عملیات متوقف شده": "eps_discontinued_operations",
        "سود زیان پایه هر سهم": "basic_eps",
        "سود زیان خالص هر سهم ریال": "net_profit_per_share",
        "سود زیان خالص هر سهم – ریال": "net_profit_per_share",
        "سرمایه": "share_capital",
    },
    "comprehensive_income": {
        "سود زیان خالص": "net_profit",
        "مازاد تجدید ارزیابی دارایی های ثابت مشهود": "revaluation_surplus_comprehensive",
        "تفاوت تسعیر ارز عملیات خارجی": "foreign_currency_translation_comprehensive",
        "سایر اقلام سود و زیان جامع سال پس از کسر مالیات": "other_comprehensive_income_after_tax",
        "سود زیان جامع سال": "comprehensive_income_total",
    },
    "balance_sheet": {
        "دارایی های ثابت مشهود": "tangible_fixed_assets",
        "سرمایه گذاری در املاک": "investment_properties",
        "دارایی های نامشهود": "intangible_assets",
        "سرمایه گذاری های بلندمدت": "long_term_investments",
        "دریافتنی های بلندمدت": "long_term_receivables",
        "دارایی مالیات انتقالی": "deferred_tax_assets",
        "سایر دارایی ها": "other_noncurrent_assets",
        "جمع دارایی های غیرجاری": "total_noncurrent_assets",
        "سفارشات و پیش پرداخت ها": "advances_and_prepayments",
        "موجودی مواد و کالا": "inventories",
        "دریافتنی های تجاری و سایر دریافتنی ها": "trade_and_other_receivables",
        "سرمایه گذاری های کوتاه مدت": "short_term_investments",
        "موجودی نقد": "cash_and_cash_equivalents",
        "دارایی های نگهداری شده برای فروش": "assets_held_for_sale",
        "جمع دارایی های جاری": "total_current_assets",
        "جمع دارایی ها": "total_assets",
        "سرمایه": "share_capital",
        "افزایش سرمایه در جریان": "capital_increase_in_progress",
        "صرف سهام": "share_premium",
        "صرف سهام خزانه": "treasury_share_premium",
        "اندوخته قانونی": "legal_reserve",
        "سایر اندوخته ها": "other_reserves",
        "مازاد تجدیدارزیابی دارایی ها": "revaluation_surplus",
        "تفاوت تسعیر ارز عملیات خارجی": "foreign_currency_translation_difference",
        "سود زیان انباشته": "retained_earnings",
        "سهام خزانه": "treasury_shares",
        "جمع حقوق مالکانه": "total_equity",
        "پرداختنی های بلندمدت": "long_term_payables",
        "تسهیلات مالی بلندمدت": "long_term_borrowings",
        "بدهی مالیات انتقالی": "deferred_tax_liabilities",
        "ذخیره مزایای پایان خدمت کارکنان": "employee_benefit_provision",
        "جمع بدهی های غیرجاری": "total_noncurrent_liabilities",
        "پرداختنی های تجاری و سایر پرداختنی ها": "trade_and_other_payables",
        "مالیات پرداختنی": "taxes_payable",
        "سود سهام پرداختنی": "dividends_payable",
        "تسهیلات مالی": "short_term_borrowings",
        "ذخایر": "provisions",
        "پیش دریافت ها": "advances_received",
        "بدهی های مرتبط با دارایی های نگهداری شده برای فروش": "liabilities_held_for_sale",
        "جمع بدهی های جاری": "total_current_liabilities",
        "جمع بدهی ها": "total_liabilities",
        "جمع حقوق مالکانه و بدهی ها": "total_equity_and_liabilities",
    },

    "cash_flow": {
        "نقد حاصل از عملیات": "cash_generated_from_operations",
        "پرداخت های نقدی بابت مالیات بر درآمد": "income_tax_paid",
        "جریان خالص ورود خروج نقد حاصل از فعالیت های عملیاتی": "net_operating_cash_flow",
        "دریافت های نقدی حاصل از فروش دارایی های ثابت مشهود": "proceeds_from_tangible_asset_sales",
        "پرداخت های نقدی برای خرید دارایی های ثابت مشهود": "purchase_of_tangible_assets",
        "دریافت های نقدی حاصل از فروش دارایی های غیرجاری نگهداری شده برای فروش": "proceeds_from_noncurrent_assets_held_for_sale",
        "دریافت های نقدی حاصل از فروش دارایی های نامشهود": "proceeds_from_intangible_asset_sales",
        "پرداخت های نقدی برای خرید دارایی های نامشهود": "purchase_of_intangible_assets",
        "دریافت های نقدی حاصل از فروش سرمایه گذاری های بلندمدت": "proceeds_from_long_term_investments",
        "پرداخت های نقدی برای تحصیل سرمایه گذاری های بلندمدت": "purchase_of_long_term_investments",
        "دریافت های نقدی حاصل از فروش سرمایه گذاری در املاک": "proceeds_from_property_investments",
        "پرداخت های نقدی برای تحصیل سرمایه گذاری در املاک": "purchase_of_property_investments",
        "دریافت های نقدی حاصل از فروش سرمایه گذاری های کوتاه مدت": "proceeds_from_short_term_investments",
        "پرداخت های نقدی برای تحصیل سرمایه گذاری های کوتاه مدت": "purchase_of_short_term_investments",
        "پرداخت های نقدی بابت تسهیلات اعطایی به دیگران": "loans_advanced",
        "دریافت های نقدی حاصل از استرداد تسهیلات اعطایی به دیگران": "loan_repayments_received",
        "دریافت های نقدی حاصل از سود تسهیلات اعطایی به دیگران": "interest_received_on_loans",
        "دریافت های نقدی حاصل از سود سهام": "dividends_received",
        "دریافت های نقدی حاصل از سود سایر سرمایه گذاری ها": "investment_income_received",
        "جریان خالص ورود خروج نقد حاصل از فعالیت های سرمایه گذاری": "net_investing_cash_flow",
        "جریان خالص ورود خروج نقد قبل از فعالیت های تامین مالی": "net_cash_flow_before_financing",
        "دریافت های نقدی حاصل از افزایش سرمایه": "proceeds_from_capital_increase",
        "دریافت های نقدی حاصل از صرف سهام": "proceeds_from_share_premium",
        "دریافت های نقدی حاصل از فروش سهام خزانه": "proceeds_from_treasury_share_sales",
        "پرداخت های نقدی برای خرید سهام خزانه": "purchase_of_treasury_shares",
        "دریافت های نقدی حاصل از تسهیلات": "borrowings_received",
        "پرداخت های نقدی بابت اصل تسهیلات": "loan_principal_repayments",
        "پرداخت های نقدی بابت سود تسهیلات": "loan_interest_paid",
        "دریافت های نقدی حاصل از انتشار اوراق مشارکت": "proceeds_from_bonds_issued",
        "پرداخت های نقدی بابت اصل اوراق مشارکت": "bond_principal_repayments",
        "پرداخت های نقدی بابت سود اوراق مشارکت": "bond_interest_paid",
        "دریافت های نقدی حاصل از انتشار اوراق خرید دین": "proceeds_from_receivables_bonds",
        "پرداخت های نقدی بابت اصل اوراق خرید دین": "receivables_bonds_principal_repayments",
        "پرداخت های نقدی بابت سود اوراق خرید دین": "receivables_bonds_interest_paid",
        "پرداخت های نقدی بابت اصل اقساط اجاره سرمایه ای": "finance_lease_principal_paid",
        "پرداخت های نقدی بابت سود اجاره سرمایه ای": "finance_lease_interest_paid",
        "پرداخت های نقدی بابت سود سهام": "dividends_paid",
        "جریان خالص ورود خروج نقد حاصل از فعالیت های تامین مالی": "net_financing_cash_flow",
        "خالص افزایش کاهش در موجودی نقد": "net_change_in_cash",
        "مانده موجودی نقد در ابتدای سال": "opening_cash_balance",
        "تاثیر تغییرات نرخ ارز": "foreign_exchange_effect_on_cash",
        "مانده موجودی نقد در پایان سال": "closing_cash_balance",
        "معاملات غیرنقدی": "non_cash_transactions",
    },

}


# Metric-specific units. Monetary metrics inherit the explicitly detected
# report unit; per-share metrics never inherit the report-wide monetary unit.
STATEMENT_METRIC_UNITS = {
    "eps_operating": "rial_per_share",
    "eps_non_operating": "rial_per_share",
    "eps_continuing_operations": "rial_per_share",
    "eps_discontinued_operations": "rial_per_share",
    "basic_eps": "rial_per_share",
    "net_profit_per_share": "rial_per_share",
}

def map_statement_metrics(
    statement_name: str,
    rows: list[dict[str, Any]],
    report_unit: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Map exact labels and attach units without modifying raw values."""
    aliases = STATEMENT_METRIC_ALIASES.get(statement_name, {})
    metrics = {}

    for row in rows:
        label = row.get("normalized_label")
        metric_key = aliases.get(label)

        if metric_key is None:
            continue

        # Keep the first occurrence; report duplicate mappings for review.
        if metric_key in metrics:
            continue

        metric = dict(row)
        unit = STATEMENT_METRIC_UNITS.get(metric_key)

        if unit is None:
            unit = report_unit if report_unit in {
                "rial", "thousand_rial", "million_rial"
            } else "unknown"

        metric["unit"] = unit
        metrics[metric_key] = metric

    return metrics


def standardize_financial_report(
    parsed_report: dict[str, Any],
) -> dict[str, Any]:
    """Add extracted rows and unambiguous standardized metrics to a parsed report.

    Original parser output and source rows are preserved. Ambiguous metric
    mappings are exposed as candidates and are not selected automatically.
    """
    if not isinstance(parsed_report, dict):
        raise ValueError("Parsed report must be a dictionary.")

    statements = parsed_report.get("statements")
    if not isinstance(statements, dict):
        raise ValueError("Parsed report must contain a statements dictionary.")

    report_unit = parsed_report.get("unit")
    standardized_statements = {}

    for statement_name, statement in statements.items():
        if not isinstance(statement, dict):
            raise ValueError(
                f"Statement must be a dictionary: {statement_name}"
            )

        extracted_rows = extract_statement_rows(statement)
        metric_candidates: dict[str, list[dict[str, Any]]] = {}

        for row in extracted_rows:
            mapped = map_statement_metrics(
                statement_name, [row], report_unit=report_unit
            )
            for metric_key, metric in mapped.items():
                metric_candidates.setdefault(metric_key, []).append(metric)

        metrics = {
            key: candidates[0]
            for key, candidates in metric_candidates.items()
            if len(candidates) == 1
        }

        mapping_issues = [
            {
                "metric_key": key,
                "reason": "ambiguous_duplicate_mapping",
                "row_indices": [
                    candidate.get("row_index") for candidate in candidates
                ],
            }
            for key, candidates in metric_candidates.items()
            if len(candidates) > 1
        ]

        standardized_statements[statement_name] = {
            **statement,
            "extracted_rows": extracted_rows,
            "metrics": metrics,
            "metric_candidates": metric_candidates,
            "mapping_issues": mapping_issues,
        }

    # Resolve equity balance roles from balance-sheet dates.
    balance_sheet = standardized_statements.get("balance_sheet", {})
    balance_metadata = balance_sheet.get("column_metadata", {})
    periods = balance_metadata.get("periods", [])

    date_roles: dict[str, set[str]] = {}

    if (
        isinstance(balance_metadata, dict)
        and balance_metadata.get("period_kind") == "point_in_time"
        and isinstance(periods, list)
    ):
        for period in periods:
            if not isinstance(period, dict):
                continue

            end_date = period.get("end_date")
            period_role = period.get("role")

            if not isinstance(end_date, str) or not end_date.strip():
                continue

            if period_role == "opening_date":
                balance_role = "opening"
            elif period_role in {
                "current_date",
                "comparative_closing_date",
            }:
                balance_role = "closing"
            else:
                continue

            normalized_date = normalize_text(end_date)
            date_roles.setdefault(normalized_date, set()).add(balance_role)

    equity_statement = standardized_statements.get("equity_changes")
    if isinstance(equity_statement, dict):
        for row in equity_statement.get("extracted_rows", []):
            row["balance_role"] = None

            if row.get("event_type") not in {
                "balance_snapshot",
                "restated_balance",
            }:
                continue

            event_date = row.get("event_date")
            if not isinstance(event_date, str):
                continue

            matching_roles = date_roles.get(normalize_text(event_date), set())
            if len(matching_roles) != 1:
                continue

            period_role = next(iter(matching_roles))
            is_restated = row.get("event_type") == "restated_balance"

            if period_role == "opening":
                row["balance_role"] = (
                    "restated_opening_balance"
                    if is_restated
                    else "opening_balance"
                )
            else:
                row["balance_role"] = (
                    "restated_closing_balance"
                    if is_restated
                    else "closing_balance"
                )

    return {
        **parsed_report,
        "statements": standardized_statements,
    }


def extract_statement_columns(
    statement_name: str, statement: dict[str, Any]
) -> dict[str, Any]:
    """Extract period and audit metadata from statement headers."""
    logical_rows = statement.get("logical_rows")
    if not isinstance(logical_rows, list) or not logical_rows:
        raise ValueError("Statement must contain logical_rows.")

    header_row = logical_rows[0]

    if statement_name == "equity_changes":
        columns = []
        for index, cell in enumerate(header_row[1:], start=1):
            label = cell.get("normalized_text", "").strip()
            if label:
                columns.append({
                    "column_index": index,
                    "label": label,
                    "normalized_label": normalize_label(label),
                    "role": "equity_component",
                })
        return {
            "statement_type": "equity_changes",
            "descriptor_column": 0,
            "columns": columns,
            "periods": [],
            "change_column": None,
        }

    if statement_name not in {
        "income_statement",
        "comprehensive_income",
        "balance_sheet",
        "cash_flow",
    }:
        raise ValueError(f"Unsupported statement name: {statement_name}")

    point_in_time = statement_name == "balance_sheet"
    period_kind = "point_in_time" if point_in_time else "duration"

    # Roles are assigned from dates after all columns have been collected.
    # Column position is not reliable: Codal reports may reorder or omit periods.

    audit_row = logical_rows[1] if len(logical_rows) > 1 else []
    periods = []
    change_column = None

    for index, cell in enumerate(header_row):
        header = cell.get("normalized_text", "").strip()
        normalized_header = normalize_label(header)

        if index == 0 or not header:
            continue

        if "درصد تغییر" in normalized_header:
            change_column = {
                "column_index": index,
                "label": header,
                "normalized_label": normalized_header,
            }
            continue

        date_match = re.search(
            r"(\d{4}/\d{2}/\d{2})",
            normalize_text(header),
        )

        audit_text = (
            audit_row[index].get("normalized_text", "").strip()
            if index < len(audit_row)
            else ""
        )
        normalized_audit = normalize_label(audit_text)

        if normalized_audit == "حسابرسی نشده":
            audit_status = "unaudited"
        elif normalized_audit == "حسابرسی شده":
            audit_status = "audited"
        else:
            audit_status = None

        periods.append({
            "column_index": index,
            "role": "unknown",
            "period_kind": period_kind,
            "end_date": date_match.group(1) if date_match else None,
            "is_restated": "تجدید ارائه شده" in normalized_header,
            "audit_status": audit_status,
            "header": header,
        })

    dated_periods = []
    for period_index, period in enumerate(periods):
        end_date = period["end_date"]
        if not end_date:
            continue
        try:
            year, month, day = (int(part) for part in end_date.split("/"))
        except (TypeError, ValueError):
            continue
        dated_periods.append((period_index, (year, month, day)))

    date_counts = {}
    for _, date_parts in dated_periods:
        date_counts[date_parts] = date_counts.get(date_parts, 0) + 1

    unique_dates = [
        (index, date_parts)
        for index, date_parts in dated_periods
        if date_counts[date_parts] == 1
    ]

    if unique_dates:
        latest_date = max(date_parts for _, date_parts in unique_dates)
        latest_indices = [
            index for index, date_parts in dated_periods
            if date_parts == latest_date
        ]

        if len(latest_indices) == 1:
            current_index = latest_indices[0]
            periods[current_index]["role"] = (
                "current_date" if point_in_time else "current_period"
            )

            older = [
                (index, date_parts)
                for index, date_parts in unique_dates
                if date_parts < latest_date
            ]

            if point_in_time:
                opening_candidates = [
                    (index, date_parts)
                    for index, date_parts in older
                    if date_parts[1:] == (1, 1)
                ]
                closing_candidates = [
                    (index, date_parts)
                    for index, date_parts in older
                    if date_parts[1:] != (1, 1)
                ]

                if opening_candidates:
                    opening_index, _ = min(
                        opening_candidates, key=lambda item: item[1]
                    )
                    periods[opening_index]["role"] = "opening_date"

                if closing_candidates:
                    closing_index, _ = max(
                        closing_candidates, key=lambda item: item[1]
                    )
                    periods[closing_index]["role"] = (
                        "comparative_closing_date"
                    )
            else:
                comparative_candidates = [
                    (index, date_parts)
                    for index, date_parts in older
                    if date_parts[1:] == latest_date[1:]
                ]
                annual_candidates = [
                    (index, date_parts)
                    for index, date_parts in older
                    if date_parts[1:] != latest_date[1:]
                ]

                if len(comparative_candidates) == 1:
                    periods[comparative_candidates[0][0]]["role"] = (
                        "comparative_period"
                    )

                if len(annual_candidates) == 1:
                    periods[annual_candidates[0][0]]["role"] = (
                        "prior_annual_period"
                    )

    return {
        "statement_type": "periodic",
        "period_kind": period_kind,
        "descriptor_column": 0,
        "periods": periods,
        "columns": [],
        "change_column": change_column,
    }
