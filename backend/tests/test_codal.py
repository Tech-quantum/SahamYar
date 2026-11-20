from decimal import Decimal

import pytest

from app.providers.codal import (
    normalize_text,
    parse_financial_number,
    parse_statement_html,
)


def test_normalize_persian_and_arabic_digits():
    assert normalize_text("فولاد ۱۴۰۵/۰۶/۳۱") == "فولاد 1405/06/31"
    assert normalize_text("١٢٣٤٥٦٧٨٩٠") == "1234567890"
    assert normalize_text("سود\u200cخالص") == "سود خالص"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("۵۹۱,۶۲۹,۲۸۶", Decimal("591629286")),
        ("(۱۱۳,۳۷۹,۹۴۳)", Decimal("-113379943")),
        ("۳۰۸", Decimal("308")),
        ("۱۲٫۵", 12.5),
        ("۱۲٪", Decimal("12")),
        ("", None),
        ("—", None),
        ("شرح حساب", None),
        ("NaN", None),
        ("Infinity", None),
    ],
)
def test_parse_financial_number(raw, expected):
    assert parse_financial_number(raw) == expected


def test_parse_five_statement_sections():
    sections = "".join(
        f"<app-statement><table><tr><th>شرح</th><th>{i}</th></tr>"
        f"<tr><td>سود</td><td>۱۲۳</td></tr></table></app-statement>"
        for i in range(5)
    )

    result = parse_statement_html(sections)

    assert list(result["statements"]) == [
        "income_statement",
        "comprehensive_income",
        "balance_sheet",
        "equity_changes",
        "cash_flow",
    ]
    assert result["statements"]["income_statement"]["row_count"] == 2
    assert result["statements"]["income_statement"]["rows"][1][1][
        "normalized_text"
    ] == "123"


def test_parser_preserves_cell_classes_and_rowspan():
    document = (
        "<app-statement><table>"
        '<tr><th rowspan="2">شرح</th><th>دوره</th></tr>'
        '<tr><th>حسابرسی نشده</th></tr>'
        '<tr><td class="dynamic_comp right-aligne">جمع</td>'
        "<td>۱۲۳</td></tr></table></app-statement>"
        + "".join(
            "<app-statement><table><tr><td>عنوان</td></tr></table>"
            for _ in range(4)
        )
    )

    result = parse_statement_html(document)
    rows = result["statements"]["income_statement"]["rows"]

    assert rows[0][0]["rowspan"] == "2"
    assert rows[2][0]["classes"] == ["dynamic_comp", "right-aligne"]


def test_parser_rejects_document_without_five_sections():
    with pytest.raises(ValueError, match="five statement sections"):
        parse_statement_html("<app-statement><table></table></app-statement>")


def test_parser_rejects_missing_primary_table():
    document = (
        "<app-statement></app-statement>"
        + "".join(
            "<app-statement><table><tr><td>x</td></tr></table></app-statement>"
            for _ in range(4)
        )
    )

    with pytest.raises(ValueError, match="income_statement"):
        parse_statement_html(document)



def test_expand_table_rows_handles_rowspan_and_colspan():
    from app.providers.codal import expand_table_rows

    def cell(text, rowspan="1", colspan="1"):
        return {
            "tag": "th",
            "classes": [],
            "rowspan": rowspan,
            "colspan": colspan,
            "text": text,
            "normalized_text": text,
        }

    rows = [
        [
            cell("شرح", rowspan="2"),
            cell("دوره جاری"),
            cell("دوره قبل"),
            cell("درصد تغییر", rowspan="2"),
        ],
        [cell("حسابرسی نشده"), cell("حسابرسی شده")],
    ]

    result = expand_table_rows(rows)

    assert len(result) == 2
    assert all(len(row) == 4 for row in result)
    assert [c["normalized_text"] for c in result[1]] == [
        "شرح", "حسابرسی نشده", "حسابرسی شده", "درصد تغییر"
    ]
    assert result[1][0]["span_origin"] is True
    assert result[1][1]["normalized_text"] == "حسابرسی نشده"


def test_report_unit_is_detected_only_from_explicit_statement():
    from app.providers.codal import _detect_report_unit

    assert _detect_report_unit(
        "<div>کلیه مبالغ درج شده به میلیون ریال می باشد</div>"
    ) == "million_rial"
    assert _detect_report_unit("<div>مبالغ به ریال</div>") is None


def test_extract_statement_rows_preserves_values_and_metadata():
    from app.providers.codal import extract_statement_rows

    statement = {
        "logical_rows": [
            [
                {"normalized_text": "شرح", "classes": [], "text": "شرح"},
                {"normalized_text": "دوره", "classes": [], "text": "دوره"},
            ],
            [
                {"normalized_text": "درآمد عملیاتی", "classes": [], "text": "درآمد عملیاتی"},
                {"normalized_text": "۱٬۲۵۰", "classes": [], "text": "۱٬۲۵۰"},
                {"normalized_text": "—", "classes": [], "text": "—"},
            ],
            [
                {"normalized_text": "سود خالص", "classes": ["dynamic_comp"], "text": "سود خالص"},
                {"normalized_text": "(۳۰۰)", "classes": ["dynamic_comp"], "text": "(۳۰۰)"},
                {"normalized_text": "", "classes": [], "text": ""},
            ],
            [
                {"normalized_text": "عنوان تکراری", "classes": [], "text": "عنوان تکراری", "span_origin": True},
                {"normalized_text": "۱۰۰", "classes": [], "text": "۱۰۰"},
            ],
            [
                {"normalized_text": "", "classes": [], "text": ""},
                {"normalized_text": "۵۰۰", "classes": [], "text": "۵۰۰"},
            ],
        ]
    }

    result = extract_statement_rows(statement)

    assert len(result) == 2
    assert result[0]["label"] == "درآمد عملیاتی"
    assert result[0]["values"] == [Decimal("1250"), None]
    assert result[0]["raw_values"] == ["۱٬۲۵۰", "—"]
    assert result[0]["is_calculated"] is False

    assert result[1]["label"] == "سود خالص"
    assert result[1]["values"] == [Decimal("-300"), None]
    assert result[1]["is_calculated"] is True


def test_extract_statement_rows_requires_logical_rows():
    from app.providers.codal import extract_statement_rows

    with pytest.raises(ValueError, match="logical_rows"):
        extract_statement_rows({})


def test_normalize_label_unifies_persian_and_arabic_variants():
    from app.providers.codal import normalize_label

    assert normalize_label("درآمدهاي عملياتي") == normalize_label("درآمدهای عملیاتی")
    assert normalize_label("هزينه هاى مالى") == normalize_label("هزینه های مالی")
    assert normalize_label("سود(زيان) خالص") == normalize_label("سود زیان خالص")


def test_extract_statement_rows_preserves_original_and_normalized_label():
    from app.providers.codal import extract_statement_rows

    result = extract_statement_rows({
        "logical_rows": [[
            {"normalized_text": "درآمدهاي عملياتي", "text": "درآمدهاي عملياتي", "classes": []},
            {"normalized_text": "۱۲۵۰", "text": "۱۲۵۰", "classes": []},
        ]]
    })

    assert result[0]["label"] == "درآمدهاي عملياتي"
    assert result[0]["normalized_label"] == "درآمدهای عملیاتی"


def test_map_statement_metrics_uses_exact_statement_specific_aliases():
    from app.providers.codal import map_statement_metrics

    rows = [
        {"label": "درآمدهاي عملياتي", "normalized_label": "درآمدهای عملیاتی", "values": [Decimal("100")]},
        {"label": "سود(زيان) خالص", "normalized_label": "سود زیان خالص", "values": [Decimal("40")]},
        {"label": "عنوان ناشناخته", "normalized_label": "عنوان ناشناخته", "values": [Decimal("20")]},
    ]

    result = map_statement_metrics("income_statement", rows)

    assert set(result) == {"operating_revenue", "net_profit"}
    assert result["operating_revenue"]["values"] == [Decimal("100")]


def test_map_statement_metrics_is_statement_specific():
    from app.providers.codal import map_statement_metrics

    rows = [
        {"normalized_label": "سرمایه", "values": [Decimal("500")]},
    ]

    income = map_statement_metrics("income_statement", rows)
    balance = map_statement_metrics("balance_sheet", rows)

    assert income["share_capital"]["values"] == [Decimal("500")]
    assert balance["share_capital"]["values"] == [Decimal("500")]
    assert map_statement_metrics("unknown_statement", rows) == {}


def test_map_statement_metrics_does_not_guess_similar_labels():
    from app.providers.codal import map_statement_metrics

    rows = [
        {"normalized_label": "سود عملیاتی", "values": [Decimal("100")]},
    ]

    assert map_statement_metrics("income_statement", rows) == {}


def test_map_statement_metrics_covers_remaining_real_report_labels():
    from app.providers.codal import map_statement_metrics

    income_rows = [
        {"normalized_label": "سود زیان خالص هر سهم – ریال", "values": [Decimal("306")]},
    ]
    balance_rows = [
        {"normalized_label": "افزایش سرمایه در جریان", "values": [Decimal("10")]},
        {"normalized_label": "صرف سهام", "values": [Decimal("20")]},
        {"normalized_label": "سایر اندوخته ها", "values": [Decimal("30")]},
        {"normalized_label": "مازاد تجدیدارزیابی دارایی ها", "values": [Decimal("40")]},
        {"normalized_label": "تفاوت تسعیر ارز عملیات خارجی", "values": [Decimal("50")]},
    ]

    income = map_statement_metrics("income_statement", income_rows)
    balance = map_statement_metrics("balance_sheet", balance_rows)

    assert income["net_profit_per_share"]["values"] == [Decimal("306")]
    assert set(balance) == {
        "capital_increase_in_progress",
        "share_premium",
        "other_reserves",
        "revaluation_surplus",
        "foreign_currency_translation_difference",
    }


def test_cash_flow_aliases_cover_all_real_report_rows():
    from app.providers.codal import map_statement_metrics

    labels = [
        "نقد حاصل از عملیات",
        "پرداخت های نقدی بابت مالیات بر درآمد",
        "جریان خالص ورود خروج نقد حاصل از فعالیت های عملیاتی",
        "دریافت های نقدی حاصل از فروش دارایی های ثابت مشهود",
        "پرداخت های نقدی برای خرید دارایی های ثابت مشهود",
        "دریافت های نقدی حاصل از فروش دارایی های غیرجاری نگهداری شده برای فروش",
        "دریافت های نقدی حاصل از فروش دارایی های نامشهود",
        "پرداخت های نقدی برای خرید دارایی های نامشهود",
        "دریافت های نقدی حاصل از فروش سرمایه گذاری های بلندمدت",
        "پرداخت های نقدی برای تحصیل سرمایه گذاری های بلندمدت",
        "دریافت های نقدی حاصل از فروش سرمایه گذاری در املاک",
        "پرداخت های نقدی برای تحصیل سرمایه گذاری در املاک",
        "دریافت های نقدی حاصل از فروش سرمایه گذاری های کوتاه مدت",
        "پرداخت های نقدی برای تحصیل سرمایه گذاری های کوتاه مدت",
        "پرداخت های نقدی بابت تسهیلات اعطایی به دیگران",
        "دریافت های نقدی حاصل از استرداد تسهیلات اعطایی به دیگران",
        "دریافت های نقدی حاصل از سود تسهیلات اعطایی به دیگران",
        "دریافت های نقدی حاصل از سود سهام",
        "دریافت های نقدی حاصل از سود سایر سرمایه گذاری ها",
        "جریان خالص ورود خروج نقد حاصل از فعالیت های سرمایه گذاری",
        "جریان خالص ورود خروج نقد قبل از فعالیت های تامین مالی",
        "دریافت های نقدی حاصل از افزایش سرمایه",
        "دریافت های نقدی حاصل از صرف سهام",
        "دریافت های نقدی حاصل از فروش سهام خزانه",
        "پرداخت های نقدی برای خرید سهام خزانه",
        "دریافت های نقدی حاصل از تسهیلات",
        "پرداخت های نقدی بابت اصل تسهیلات",
        "پرداخت های نقدی بابت سود تسهیلات",
        "دریافت های نقدی حاصل از انتشار اوراق مشارکت",
        "پرداخت های نقدی بابت اصل اوراق مشارکت",
        "پرداخت های نقدی بابت سود اوراق مشارکت",
        "دریافت های نقدی حاصل از انتشار اوراق خرید دین",
        "پرداخت های نقدی بابت اصل اوراق خرید دین",
        "پرداخت های نقدی بابت سود اوراق خرید دین",
        "پرداخت های نقدی بابت اصل اقساط اجاره سرمایه ای",
        "پرداخت های نقدی بابت سود اجاره سرمایه ای",
        "پرداخت های نقدی بابت سود سهام",
        "جریان خالص ورود خروج نقد حاصل از فعالیت های تامین مالی",
        "خالص افزایش کاهش در موجودی نقد",
        "مانده موجودی نقد در ابتدای سال",
        "تاثیر تغییرات نرخ ارز",
        "مانده موجودی نقد در پایان سال",
        "معاملات غیرنقدی",
    ]

    rows = [{"normalized_label": label, "values": [Decimal("1")]} for label in labels]
    result = map_statement_metrics("cash_flow", rows)

    assert len(result) == 43
    assert len(set(result)) == 43
    assert result["net_operating_cash_flow"]["values"] == [Decimal("1")]
    assert result["non_cash_transactions"]["values"] == [Decimal("1")]


def _header_cell(text, span_origin=False):
    return {
        "normalized_text": text,
        "text": text,
        "span_origin": span_origin,
    }


def test_extract_statement_columns_identifies_periods():
    from app.providers.codal import extract_statement_columns

    statement = {"logical_rows": [
        [
            _header_cell("شرح"),
            _header_cell("دوره منتهي به ۱۴۰۵/۰۶/۳۱"),
            _header_cell("تجديد ارائه شده دوره منتهي به ۱۴۰۴/۰۶/۳۱"),
            _header_cell("تجديد ارائه شده دوره منتهي به ۱۴۰۴/۱۲/۲۹"),
            _header_cell("درصد تغيير"),
        ],
        [
            _header_cell("شرح", True),
            _header_cell("حسابرسی نشده"),
            _header_cell("حسابرسی شده"),
            _header_cell("حسابرسی شده"),
            _header_cell("درصد تغيير", True),
        ],
    ]}

    result = extract_statement_columns("income_statement", statement)

    assert result["period_kind"] == "duration"
    assert [p["end_date"] for p in result["periods"]] == [
        "1405/06/31", "1404/06/31", "1404/12/29"
    ]
    assert [p["role"] for p in result["periods"]] == [
        "current_period", "comparative_period", "prior_annual_period"
    ]
    assert [p["audit_status"] for p in result["periods"]] == [
        "unaudited", "audited", "audited"
    ]
    assert [p["is_restated"] for p in result["periods"]] == [
        False, True, True
    ]
    assert result["change_column"]["column_index"] == 4


def test_extract_statement_columns_distinguishes_balance_dates():
    from app.providers.codal import extract_statement_columns

    statement = {"logical_rows": [
        [
            _header_cell("شرح"),
            _header_cell("به تاريخ ۱۴۰۵/۰۶/۳۱"),
            _header_cell("تجديد ارائه شده به تاريخ ۱۴۰۴/۱۲/۲۹"),
            _header_cell("تجديد ارائه شده به تاريخ ۱۴۰۴/۰۱/۰۱"),
            _header_cell("درصد تغيير"),
        ],
        [
            _header_cell("شرح", True),
            _header_cell("حسابرسی نشده"),
            _header_cell("حسابرسی شده"),
            _header_cell("حسابرسی شده"),
            _header_cell("درصد تغيير", True),
        ],
    ]}

    result = extract_statement_columns("balance_sheet", statement)

    assert result["period_kind"] == "point_in_time"
    assert [p["role"] for p in result["periods"]] == [
        "current_date", "comparative_closing_date", "opening_date"
    ]
    assert result["periods"][2]["end_date"] == "1404/01/01"


def test_extract_statement_columns_handles_equity_components():
    from app.providers.codal import extract_statement_columns

    statement = {"logical_rows": [[
        _header_cell("شرح"),
        _header_cell("سرمایه"),
        _header_cell("سود انباشته"),
        _header_cell("جمع کل"),
    ]]}

    result = extract_statement_columns("equity_changes", statement)

    assert result["statement_type"] == "equity_changes"
    assert result["periods"] == []
    assert result["change_column"] is None
    assert len(result["columns"]) == 3
    assert all(
        column["role"] == "equity_component"
        for column in result["columns"]
    )


def test_parse_statement_html_includes_column_metadata():
    sections = "".join(
        (
            "<app-statement><table>"
            "<tr><th>شرح</th><th>دوره منتهی به ۱۴۰۵/۰۶/۳۱</th></tr>"
            "<tr><td>سود خالص</td><td>۱۲۳</td></tr>"
            "</table></app-statement>"
        )
        for _ in range(5)
    )

    result = parse_statement_html(sections)
    statement = result["statements"]["income_statement"]

    assert "column_metadata" in statement
    assert statement["column_metadata"]["statement_type"] == "periodic"
    assert statement["column_metadata"]["periods"][0]["end_date"] == "1405/06/31"


def test_comprehensive_income_maps_unique_labels_and_preserves_duplicates():
    from app.providers.codal import map_statement_metrics

    labels = [
        "سود زیان خالص",
        "مازاد تجدید ارزیابی دارایی های ثابت مشهود",
        "تفاوت تسعیر ارز عملیات خارجی",
        "سایر",
        "مالیات بر درآمد اقلام فوق",
        "جمع",
        "سایر اقلام سود و زیان جامع سال پس از کسر مالیات",
        "سود زیان جامع سال",
        "سایر",
        "مالیات بر درآمد اقلام فوق",
        "جمع",
    ]
    rows = [
        {
            "row_index": index,
            "label": label,
            "normalized_label": label,
            "values": [Decimal(index)],
        }
        for index, label in enumerate(labels)
    ]

    result = map_statement_metrics("comprehensive_income", rows)

    assert set(result) == {
        "net_profit",
        "revaluation_surplus_comprehensive",
        "foreign_currency_translation_comprehensive",
        "other_comprehensive_income_after_tax",
        "comprehensive_income_total",
    }
    assert result["net_profit"]["row_index"] == 0
    assert result["comprehensive_income_total"]["row_index"] == 7
    assert len(rows) == 11
    assert [row["label"] for row in rows].count("سایر") == 2


def test_extract_statement_rows_separates_period_values_and_change_percent():
    from app.providers.codal import extract_statement_rows

    statement = {
        "column_metadata": {
            "periods": [
                {"column_index": 1, "role": "current_period"},
                {"column_index": 2, "role": "comparative_period"},
                {"column_index": 3, "role": "prior_annual_period"},
            ],
            "change_column": {"column_index": 4},
        },
        "logical_rows": [[
            {"normalized_text": "سود خالص", "text": "سود خالص", "classes": []},
            {"normalized_text": "۱۰۰", "text": "۱۰۰", "classes": []},
            {"normalized_text": "۸۰", "text": "۸۰", "classes": []},
            {"normalized_text": "۳۰۰", "text": "۳۰۰", "classes": []},
            {"normalized_text": "۲۵", "text": "۲۵", "classes": []},
        ]],
    }

    result = extract_statement_rows(statement)[0]

    assert result["values"] == [
        Decimal("100"), Decimal("80"), Decimal("300"), Decimal("25")
    ]
    assert result["period_values"] == {
        "current_period": Decimal("100"),
        "comparative_period": Decimal("80"),
        "prior_annual_period": Decimal("300"),
    }
    assert result["change_percent"] == Decimal("25")
    assert result["period_raw_values"] == {
        "current_period": "۱۰۰",
        "comparative_period": "۸۰",
        "prior_annual_period": "۳۰۰",
    }
    assert result["change_percent_raw"] == "۲۵"


def test_extract_equity_changes_maps_values_by_component_name():
    from app.providers.codal import extract_statement_rows

    statement = {
        "column_metadata": {
            "statement_type": "equity_changes",
            "columns": [
                {"column_index": 1, "normalized_label": "سرمایه"},
                {"column_index": 2, "normalized_label": "سود انباشته"},
                {"column_index": 3, "normalized_label": "جمع کل"},
            ],
            "periods": [],
            "change_column": None,
        },
        "logical_rows": [[
            {"normalized_text": "مانده پایان دوره", "text": "مانده پایان دوره", "classes": []},
            {"normalized_text": "۱۰۰۰", "text": "۱۰۰۰", "classes": []},
            {"normalized_text": "۲۵۰", "text": "۲۵۰", "classes": []},
            {"normalized_text": "۱۲۵۰", "text": "۱۲۵۰", "classes": []},
        ]],
    }

    result = extract_statement_rows(statement)[0]

    assert result["values"] == [
        Decimal("1000"), Decimal("250"), Decimal("1250")
    ]
    assert result["equity_component_values"] == {
        "سرمایه": Decimal("1000"),
        "سود انباشته": Decimal("250"),
        "جمع کل": Decimal("1250"),
    }
    assert result["equity_component_raw_values"] == {
        "سرمایه": "۱۰۰۰",
        "سود انباشته": "۲۵۰",
        "جمع کل": "۱۲۵۰",
    }
    assert result["period_values"] == {}
    assert result["change_percent"] is None


def test_metric_units_distinguish_money_from_per_share_values():
    from app.providers.codal import map_statement_metrics

    rows = [
        {"normalized_label": "درآمدهای عملیاتی", "values": [Decimal("250")]},
        {"normalized_label": "سود زیان پایه هر سهم", "values": [Decimal("308")]},
        {"normalized_label": "سود زیان خالص هر سهم ریال", "values": [Decimal("306")]},
    ]

    result = map_statement_metrics(
        "income_statement", rows, report_unit="million_rial"
    )

    assert result["operating_revenue"]["unit"] == "million_rial"
    assert result["basic_eps"]["unit"] == "rial_per_share"
    assert result["net_profit_per_share"]["unit"] == "rial_per_share"


def test_metric_units_are_unknown_when_report_unit_is_missing():
    from app.providers.codal import map_statement_metrics

    rows = [
        {"normalized_label": "درآمدهای عملیاتی", "values": [Decimal("100")]},
    ]

    result = map_statement_metrics("income_statement", rows)

    assert result["operating_revenue"]["unit"] == "unknown"
    assert "raw_unit" not in result["operating_revenue"]


def test_metric_units_reject_unsupported_report_units():
    from app.providers.codal import map_statement_metrics

    rows = [
        {"normalized_label": "درآمدهای عملیاتی", "values": [Decimal("100")]},
    ]

    result = map_statement_metrics(
        "income_statement", rows, report_unit="unknown_unit"
    )

    assert result["operating_revenue"]["unit"] == "unknown"


def test_metric_unit_metadata_preserves_original_decimal_values():
    from app.providers.codal import map_statement_metrics

    original = Decimal("2509422184")
    rows = [
        {"normalized_label": "درآمدهای عملیاتی", "values": [original]},
    ]

    result = map_statement_metrics(
        "income_statement", rows, report_unit="million_rial"
    )

    assert result["operating_revenue"]["values"][0] is original
    assert result["operating_revenue"]["values"][0] == Decimal("2509422184")


def test_standardize_financial_report_preserves_source_and_maps_metrics():
    from app.providers.codal import standardize_financial_report

    report = {
        "source": "Codal",
        "parser_version": 1,
        "unit": "million_rial",
        "statements": {
            "income_statement": {
                "logical_rows": [[
                    {"normalized_text": "درآمدهای عملیاتی", "text": "درآمدهای عملیاتی", "classes": []},
                    {"normalized_text": "۲۵۰", "text": "۲۵۰", "classes": []},
                ]],
                "column_metadata": {"periods": [], "change_column": None},
            }
        },
    }

    result = standardize_financial_report(report)
    statement = result["statements"]["income_statement"]

    assert result["source"] == "Codal"
    assert result["unit"] == "million_rial"
    assert statement["logical_rows"] == report["statements"]["income_statement"]["logical_rows"]
    assert statement["extracted_rows"][0]["values"] == [Decimal("250")]
    assert statement["metrics"]["operating_revenue"]["unit"] == "million_rial"
    assert statement["metric_candidates"]["operating_revenue"][0]["values"] == [Decimal("250")]
    assert statement["mapping_issues"] == []


def test_standardize_financial_report_does_not_choose_ambiguous_metrics():
    from app.providers.codal import standardize_financial_report

    report = {
        "unit": "million_rial",
        "statements": {
            "income_statement": {
                "logical_rows": [
                    [
                        {"normalized_text": "درآمدهای عملیاتی", "text": "درآمدهای عملیاتی", "classes": []},
                        {"normalized_text": "۱۰۰", "text": "۱۰۰", "classes": []},
                    ],
                    [
                        {"normalized_text": "درآمدهای عملیاتی", "text": "درآمدهای عملیاتی", "classes": []},
                        {"normalized_text": "۲۰۰", "text": "۲۰۰", "classes": []},
                    ],
                ],
                "column_metadata": {"periods": [], "change_column": None},
            }
        },
    }

    statement = standardize_financial_report(report)["statements"]["income_statement"]

    assert "operating_revenue" not in statement["metrics"]
    assert len(statement["metric_candidates"]["operating_revenue"]) == 2
    assert statement["mapping_issues"] == [{
        "metric_key": "operating_revenue",
        "reason": "ambiguous_duplicate_mapping",
        "row_indices": [0, 1],
    }]


def test_change_percent_has_independent_percent_unit():
    from app.providers.codal import extract_statement_rows

    statement = {
        "column_metadata": {
            "periods": [],
            "change_column": {"column_index": 1},
        },
        "logical_rows": [[
            {"normalized_text": "درآمد", "text": "درآمد", "classes": []},
            {"normalized_text": "۲۵", "text": "۲۵", "classes": []},
        ]],
    }

    row = extract_statement_rows(statement)[0]

    assert row["change_percent"] == Decimal("25")
    assert row["change_percent_unit"] == "percent"


def test_equity_components_preserve_zero_blank_and_negative_values():
    from app.providers.codal import extract_statement_rows

    statement = {
        "column_metadata": {
            "statement_type": "equity_changes",
            "columns": [
                {"column_index": 1, "normalized_label": "سرمایه"},
                {"column_index": 2, "normalized_label": "سود انباشته"},
                {"column_index": 3, "normalized_label": "سهام خزانه"},
            ],
            "periods": [],
            "change_column": None,
        },
        "logical_rows": [[
            {"normalized_text": "مانده پایان دوره", "text": "مانده پایان دوره", "classes": []},
            {"normalized_text": "۰", "text": "۰ ", "classes": []},
            {"normalized_text": "", "text": " ", "classes": []},
            {"normalized_text": "(۲۳,۸۱۱,۱۹۸)", "text": "(۲۳,۸۱۱,۱۹۸) ", "classes": []},
        ]],
    }

    result = extract_statement_rows(statement)[0]

    assert result["equity_component_values"] == {
        "سرمایه": Decimal("0"),
        "سود انباشته": None,
        "سهام خزانه": Decimal("-23811198"),
    }
    assert result["equity_component_raw_values"] == {
        "سرمایه": "۰ ",
        "سود انباشته": " ",
        "سهام خزانه": "(۲۳,۸۱۱,۱۹۸) ",
    }


def test_extract_statement_columns_assigns_duration_roles_by_dates_not_order():
    from app.providers.codal import extract_statement_columns

    statement = {"logical_rows": [
        [
            _header_cell("شرح"),
            _header_cell("تجدید ارائه شده دوره منتهی به ۱۴۰۴/۱۲/۲۹"),
            _header_cell("دوره منتهی به ۱۴۰۵/۰۶/۳۱"),
            _header_cell("تجدید ارائه شده دوره منتهی به ۱۴۰۴/۰۶/۳۱"),
        ],
        [
            _header_cell("شرح", True),
            _header_cell("حسابرسی شده"),
            _header_cell("حسابرسی نشده"),
            _header_cell("حسابرسی شده"),
        ],
    ]}

    result = extract_statement_columns("income_statement", statement)
    roles_by_date = {
        period["end_date"]: period["role"]
        for period in result["periods"]
    }

    assert roles_by_date == {
        "1404/12/29": "prior_annual_period",
        "1405/06/31": "current_period",
        "1404/06/31": "comparative_period",
    }


def test_extract_statement_columns_does_not_invent_missing_comparative_period():
    from app.providers.codal import extract_statement_columns

    statement = {"logical_rows": [[
        _header_cell("شرح"),
        _header_cell("دوره منتهی به ۱۴۰۵/۰۶/۳۱"),
        _header_cell("تجدید ارائه شده دوره منتهی به ۱۴۰۴/۱۲/۲۹"),
    ]]}

    result = extract_statement_columns("income_statement", statement)
    roles_by_date = {
        period["end_date"]: period["role"]
        for period in result["periods"]
    }

    assert roles_by_date == {
        "1405/06/31": "current_period",
        "1404/12/29": "prior_annual_period",
    }


def test_extract_statement_columns_assigns_balance_roles_by_dates_not_order():
    from app.providers.codal import extract_statement_columns

    statement = {"logical_rows": [[
        _header_cell("شرح"),
        _header_cell("به تاریخ ۱۴۰۴/۰۱/۰۱"),
        _header_cell("به تاریخ ۱۴۰۵/۰۶/۳۱"),
        _header_cell("تجدید ارائه شده به تاریخ ۱۴۰۴/۱۲/۲۹"),
    ]]}

    result = extract_statement_columns("balance_sheet", statement)
    roles_by_date = {
        period["end_date"]: period["role"]
        for period in result["periods"]
    }

    assert roles_by_date == {
        "1404/01/01": "opening_date",
        "1405/06/31": "current_date",
        "1404/12/29": "comparative_closing_date",
    }


def test_equity_event_classification_is_label_based_and_preserves_unknown_rows():
    from app.providers.codal import extract_statement_rows

    cases = [
        ("مانده در ۱۴۰۴/۰۱/۰۱", "balance_snapshot", "1404/01/01"),
        ("مانده تجديد ارائه شده در ۱۴۰۴/۱۲/۲۹", "restated_balance", "1404/12/29"),
        ("سود(زيان) خالص گزارش شده در صورت هاي مالي سال ۱۴۰۴/۱۲/۲۹", "reported_net_profit", "1404/12/29"),
        ("سود (زيان) خالص در دوره ۶ ماهه منتهي به ۱۴۰۵/۰۶/۳۱", "current_period_profit", "1405/06/31"),
        ("افزايش سرمايه در جريان", "capital_increase_in_progress", None),
        ("خريد سهام خزانه", "treasury_share_purchase", None),
        ("تخصيص به اندوخته قانوني", "reserve_allocation", None),
        ("تخصيص به ساير اندوخته ها", "reserve_allocation", None),
        ("شرح ناشناخته", "unknown", None),
    ]

    statement = {
        "column_metadata": {
            "statement_type": "equity_changes",
            "columns": [],
            "periods": [],
            "change_column": None,
        },
        "logical_rows": [
            [
                {"normalized_text": label, "text": label, "classes": []},
                {"normalized_text": "۰", "text": "۰", "classes": []},
            ]
            for label, _, _ in cases
        ],
    }

    rows = extract_statement_rows(statement)
    assert [(r["event_type"], r["event_date"]) for r in rows] == [
        (event_type, event_date)
        for _, event_type, event_date in cases
    ]


def test_standardize_equity_balance_roles_from_balance_sheet_dates():
    from app.providers.codal import standardize_financial_report

    def cell(value):
        return {"normalized_text": value, "text": value, "classes": []}

    equity_labels = [
        "مانده در ۱۴۰۴/۰۱/۰۱",
        "مانده تجدید ارائه شده در ۱۴۰۴/۰۱/۰۱",
        "مانده تجدید ارائه شده در ۱۴۰۴/۱۲/۲۹",
        "مانده در ۱۴۰۵/۰۶/۳۱",
        "سود (زیان) خالص در دوره ۶ ماهه منتهی به ۱۴۰۵/۰۶/۳۱",
        "مانده در ۱۴۰۶/۰۱/۰۱",
    ]

    report = {
        "unit": "million_rial",
        "statements": {
            "equity_changes": {
                "logical_rows": [
                    [cell("شرح"), cell("جمع کل")],
                    *[[cell(label), cell("۱۰۰")] for label in equity_labels],
                ],
                "column_metadata": {
                    "statement_type": "equity_changes",
                    "columns": [
                        {
                            "column_index": 1,
                            "label": "جمع کل",
                            "normalized_label": "جمع کل",
                            "role": "equity_component",
                        }
                    ],
                    "periods": [],
                    "change_column": None,
                },
            },
            "balance_sheet": {
                "logical_rows": [
                    [cell("شرح"), cell("دوره جاری")],
                    [cell("دارایی‌ها"), cell("۱۰۰")],
                ],
                "column_metadata": {
                    "statement_type": "periodic",
                    "period_kind": "point_in_time",
                    "periods": [
                        {
                            "end_date": "1405/06/31",
                            "role": "current_date",
                            "is_restated": False,
                        },
                        {
                            "end_date": "1404/12/29",
                            "role": "comparative_closing_date",
                            "is_restated": True,
                        },
                        {
                            "end_date": "1404/01/01",
                            "role": "opening_date",
                            "is_restated": True,
                        },
                    ],
                },
            },
        },
    }

    result = standardize_financial_report(report)
    rows = result["statements"]["equity_changes"]["extracted_rows"]

    assert [row.get("balance_role") for row in rows] == [
        "opening_balance",
        "restated_opening_balance",
        "restated_closing_balance",
        "closing_balance",
        None,
        None,
    ]
    assert [row["event_type"] for row in rows[:4]] == [
        "balance_snapshot",
        "restated_balance",
        "restated_balance",
        "balance_snapshot",
    ]
    assert rows[4]["event_type"] == "current_period_profit"


def test_equity_balance_role_is_none_for_conflicting_balance_sheet_dates():
    from app.providers.codal import standardize_financial_report

    def cell(value):
        return {"normalized_text": value, "text": value, "classes": []}

    report = {
        "unit": "million_rial",
        "statements": {
            "equity_changes": {
                "logical_rows": [
                    [cell("شرح"), cell("جمع کل")],
                    [cell("مانده در ۱۴۰۵/۰۶/۳۱"), cell("۱۰۰")],
                ],
                "column_metadata": {
                    "statement_type": "equity_changes",
                    "columns": [
                        {
                            "column_index": 1,
                            "label": "جمع کل",
                            "normalized_label": "جمع کل",
                            "role": "equity_component",
                        }
                    ],
                    "periods": [],
                    "change_column": None,
                },
            },
            "balance_sheet": {
                "logical_rows": [
                    [cell("شرح"), cell("دوره جاری")],
                    [cell("دارایی‌ها"), cell("۱۰۰")],
                ],
                "column_metadata": {
                    "statement_type": "periodic",
                    "period_kind": "point_in_time",
                    "periods": [
                        {
                            "end_date": "1405/06/31",
                            "role": "current_date",
                            "is_restated": False,
                        },
                        {
                            "end_date": "1405/06/31",
                            "role": "opening_date",
                            "is_restated": False,
                        },
                    ],
                },
            },
        },
    }

    result = standardize_financial_report(report)
    rows = result["statements"]["equity_changes"]["extracted_rows"]

    assert len(rows) == 1
    assert rows[0]["event_type"] == "balance_snapshot"
    assert rows[0]["balance_role"] is None
