"""Тесты денежных и календарных утилит."""

import datetime
from decimal import Decimal

import pytest

from pyalimony.errors import ConfigError
from pyalimony.utils import (
    add_months,
    format_date,
    format_money,
    format_percent,
    full_months_between,
    parse_date,
    percent_of,
    plural,
    quantize_money,
    to_decimal,
    to_money,
)


@pytest.mark.parametrize(
    ("amount", "percent", "expected"),
    [
        ("100", "10", "10.00"),
        ("100000", "25", "25000.00"),
        ("100000", "16.6", "16600.00"),
        ("70000", "16.6", "11620.00"),
        ("100000", "70", "70000.00"),
        ("100000", "0", "0.00"),
        ("0", "40", "0.00"),
        ("123456", "33.3", "41110.85"),
    ],
)
def test_percent_of(amount, percent, expected):
    assert percent_of(Decimal(amount), Decimal(percent)) == Decimal(expected)


def test_percent_of_is_exact_where_float_was_not():
    """Тот самый случай, на котором float давал 11620.000000000002."""
    assert percent_of(Decimal("70000"), Decimal("16.6")) == Decimal("11620.00")


def test_percent_of_third_share_rounds_half_up():
    """1/3 от 100000 — 33333.33, половина копейки округляется вверх."""
    third = Decimal("100") / Decimal("3")
    assert percent_of(Decimal("100000"), third) == Decimal("33333.33")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("2.5", "2.50"), ("2.505", "2.51"), ("2.515", "2.52"), ("-2.505", "-2.51")],
)
def test_quantize_money_is_half_up_not_bankers(raw, expected):
    assert quantize_money(Decimal(raw)) == Decimal(expected)


@pytest.mark.parametrize("raw", [100000, 100000.0, "100000", " 100 000 ".replace(" ", ""), Decimal("100000")])
def test_to_decimal_accepts_numbers_and_strings(raw):
    assert to_decimal(raw, "field") == Decimal("100000")


def test_to_decimal_accepts_comma_separator():
    assert to_decimal("16,6", "field") == Decimal("16.6")


def test_to_decimal_avoids_float_artifacts():
    """0.1 + 0.2 во float даёт 0.30000000000000004; через строку — ровно 0.3."""
    assert to_decimal(0.3, "field") == Decimal("0.3")


@pytest.mark.parametrize("raw", [None, True, [], {}, "abc"])
def test_to_decimal_rejects_garbage(raw):
    with pytest.raises(ConfigError):
        to_decimal(raw, "some_field")


def test_to_decimal_error_names_the_field():
    with pytest.raises(ConfigError, match="net_income"):
        to_decimal("abc", "net_income")


def test_to_money_rounds_to_kopecks():
    assert to_money("100.005", "field") == Decimal("100.01")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("30.11.2006", datetime.date(2006, 11, 30)),
        ("2006-11-30", datetime.date(2006, 11, 30)),
        ("  30.11.2006  ", datetime.date(2006, 11, 30)),
        (datetime.date(2006, 11, 30), datetime.date(2006, 11, 30)),
        (datetime.datetime(2006, 11, 30, 12, 0), datetime.date(2006, 11, 30)),
    ],
)
def test_parse_date(raw, expected):
    assert parse_date(raw, "birthday") == expected


@pytest.mark.parametrize("raw", ["30/11/2006", "31.02.2006", "не дата", 42, None])
def test_parse_date_rejects_garbage(raw):
    with pytest.raises(ConfigError, match="birthday"):
        parse_date(raw, "birthday")


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        ((2026, 3, 1), 4, (2026, 7, 1)),
        ((2026, 3, 1), 0, (2026, 3, 1)),
        ((2026, 12, 15), 1, (2027, 1, 15)),
        ((2026, 1, 31), 1, (2026, 2, 28)),
        ((2024, 1, 31), 1, (2024, 2, 29)),
        ((2026, 7, 15), -7, (2025, 12, 15)),
        ((2026, 3, 1), 24, (2028, 3, 1)),
    ],
)
def test_add_months(start, months, expected):
    assert add_months(datetime.date(*start), months) == datetime.date(*expected)


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ((2026, 3, 1), (2026, 7, 31), 4),
        ((2026, 3, 1), (2026, 3, 1), 0),
        ((2026, 3, 15), (2026, 7, 14), 3),
        ((2026, 3, 15), (2026, 7, 15), 4),
        ((2026, 12, 1), (2027, 1, 1), 1),
        ((2026, 3, 1), (2025, 1, 1), 0),
        ((2020, 1, 1), (2026, 1, 1), 72),
    ],
)
def test_full_months_between(start, end, expected):
    assert full_months_between(datetime.date(*start), datetime.date(*end)) == expected


def test_full_months_between_survives_new_year():
    """Регрессия: старая формула по номерам месяцев в январе уходила в минус."""
    assert full_months_between(datetime.date(2026, 3, 1), datetime.date(2027, 1, 1)) == 10


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, "месяцев"), (1, "месяц"), (2, "месяца"), (4, "месяца"), (5, "месяцев"), (11, "месяцев"), (21, "месяц")],
)
def test_plural(count, expected):
    assert plural(count, "месяц", "месяца", "месяцев") == expected


def test_format_money_groups_thousands():
    assert format_money(Decimal("1234567.891")) == "1 234 567.89"


def test_format_percent():
    assert format_percent(Decimal("100") / Decimal("3")) == "33.33 %"


def test_format_date():
    assert format_date(datetime.date(2006, 11, 30)) == "30.11.2006"
