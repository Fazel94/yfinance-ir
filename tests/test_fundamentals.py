import pandas as pd
import pytest
from conftest import load_fixture

from yfinance_ir.exceptions import DataUnavailable
from yfinance_ir.fundamentals import parse_datasource, statements
from yfinance_ir.sources import codal


def _cell(row, column, value, *, period=None, group="Body"):
    return {
        "rowSequence": row,
        "columnSequence": column,
        "value": value,
        "cellGroupName": group,
        "periodEndToDate": period or "",
        "yearEndToDate": "",
    }


def _datasource(cells):
    return {"sheets": [{"tables": [{"cells": cells}]}]}


def test_real_codal_income_statement_parses_into_periods_and_line_items():
    frame = parse_datasource(load_fixture("codal_income_folad.json"))

    assert not frame.empty
    assert all(isinstance(column, pd.Timestamp) for column in frame.columns)
    assert list(frame.columns) == sorted(frame.columns, reverse=True)
    revenue = [label for label in frame.index if "درآمد" in label or "فروش" in label]
    assert revenue, f"no revenue line among {list(frame.index)[:10]}"
    assert frame.loc[revenue[0]].dropna().abs().max() > 0


def test_percentage_columns_without_a_period_are_dropped():
    cells = [
        _cell(1, 1, "شرح", group="Header"),
        _cell(1, 2, "1403/12/30", period="1403/12/30", group="Header"),
        _cell(1, 3, "درصد تغییر", group="Header"),
        _cell(2, 1, "درآمد عملیاتی"),
        _cell(2, 2, "1000"),
        _cell(2, 3, "25"),
    ]

    frame = parse_datasource(_datasource(cells))

    assert list(frame.columns) == [pd.Timestamp("2025-03-20")]
    assert frame.loc["درآمد عملیاتی"].iloc[0] == 1000


def test_parenthesised_and_grouped_numbers_become_signed_floats():
    cells = [
        _cell(1, 2, "1403/12/30", period="1403/12/30", group="Header"),
        _cell(2, 1, "بهای تمام شده"),
        _cell(2, 2, "(1,234)"),
        _cell(3, 1, "سود ناخالص"),
        _cell(3, 2, "۲,۵۰۰"),
    ]

    frame = parse_datasource(_datasource(cells))

    assert frame.loc["بهای تمام شده"].iloc[0] == -1234
    assert frame.loc["سود ناخالص"].iloc[0] == 2500


def test_a_restated_all_zero_column_loses_to_the_populated_one():
    cells = [
        _cell(1, 2, "1403/12/30", period="1403/12/30", group="Header"),
        _cell(1, 3, "1403/12/30", period="1403/12/30", group="Header"),
        _cell(2, 1, "درآمد عملیاتی"),
        _cell(2, 2, "0"),
        _cell(2, 3, "7777"),
    ]

    frame = parse_datasource(_datasource(cells))

    assert frame.loc["درآمد عملیاتی"].iloc[0] == 7777


def test_section_headers_without_numbers_are_not_rows():
    cells = [
        _cell(1, 2, "1403/12/30", period="1403/12/30", group="Header"),
        _cell(2, 1, "عملیات در حال تداوم:"),
        _cell(3, 1, "درآمد عملیاتی"),
        _cell(3, 2, "10"),
    ]

    frame = parse_datasource(_datasource(cells))

    assert list(frame.index) == ["درآمد عملیاتی"]


def test_the_latest_filing_wins_a_period_reported_twice(api, session):
    letters = [
        {"Url": "/Reports/Decision.aspx?LetterSerial=old", "PublishDateTime": "۱۴۰۴/۰۱/۰۱ ۰۸:۰۰:۰۰",
         "Title": "صورت‌های مالی سال مالی منتهی به 1403/12/30"},
        {"Url": "/Reports/Decision.aspx?LetterSerial=new", "PublishDateTime": "۱۴۰۵/۰۵/۰۷ ۲۰:۱۷:۰۱",
         "Title": "صورت‌های مالی سال مالی منتهی به 1403/12/30"},
    ]
    api.codal_search(letters)
    api.mock.add(
        "GET",
        codal.BASE + "/Reports/Decision.aspx",
        body='<script>\nvar datasource = {"sheets":[{"tables":[{"cells":['
        '{"rowSequence":1,"columnSequence":2,"value":"1403/12/30","cellGroupName":"Header",'
        '"periodEndToDate":"1403/12/30"},'
        '{"rowSequence":2,"columnSequence":1,"value":"درآمد عملیاتی","cellGroupName":"Body",'
        '"periodEndToDate":""},'
        '{"rowSequence":2,"columnSequence":2,"value":"999","cellGroupName":"Body",'
        '"periodEndToDate":""}]}]}]};\n</script>',
        content_type="text/html",
    )

    frame = statements(session, "فولاد", codal.SHEET_INCOME)

    # both letters cover 1403/12/30; only one column may survive
    assert list(frame.columns) == [pd.Timestamp("2025-03-20")]
    # and it must come from the newest publication, which is requested first
    assert "LetterSerial=new" in api.mock.calls[1].request.url


def test_no_filings_raises(api, session):
    api.codal_search([])

    with pytest.raises(DataUnavailable, match="no Codal filings"):
        statements(session, "ناشناخته", codal.SHEET_INCOME)


def test_persian_digits_are_normalised():
    assert codal.fa_digits("۱۴۰۵/۰۵/۰۷") == "1405/05/07"
