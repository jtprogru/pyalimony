"""Тесты истории дохода с точностью до дня."""

import datetime
from decimal import Decimal

import pytest

from pyalimony.income import (
    KIND_ACTUAL,
    KIND_MIXED,
    KIND_NONE,
    KIND_SALARY,
    KIND_UNEMPLOYED,
    IncomePeriod,
    IncomeTimeline,
    single_period,
)


def period(start, end, net=None, unemployed=False):
    return IncomePeriod(
        start=datetime.date(*start),
        end=datetime.date(*end) if end else None,
        net_monthly=None if unemployed else Decimal(net),
    )


@pytest.fixture
def timeline():
    """Тот самый апрель: 5 дней работы, 22 дня без заработка, 3 дня на новой работе."""
    return IncomeTimeline(
        periods=(
            period((2024, 9, 1), (2026, 4, 5), "140000"),
            period((2026, 4, 6), (2026, 4, 27), unemployed=True),
            period((2026, 4, 28), None, "210000"),
        ),
        average_wage=Decimal("87000"),
    )


def test_full_month_of_salary(timeline):
    income = timeline.income_for_month(2026, 3)
    assert income.amount == Decimal("140000.00")
    assert income.kind == KIND_SALARY
    assert income.unemployed_days == 0


def test_split_month_sums_segments(timeline):
    """140000*5/30 + 87000*22/30 + 210000*3/30."""
    income = timeline.income_for_month(2026, 4)
    assert income.amount == Decimal("108133.33")
    assert income.kind == KIND_MIXED
    assert income.unemployed_days == 22


def test_month_after_the_gap(timeline):
    income = timeline.income_for_month(2026, 5)
    assert income.amount == Decimal("210000.00")
    assert income.kind == KIND_SALARY


def test_open_period_covers_the_future(timeline):
    assert timeline.income_for_month(2030, 12).amount == Decimal("210000.00")


def test_month_before_the_timeline_is_empty(timeline):
    income = timeline.income_for_month(2024, 8)
    assert income.amount == Decimal("0.00")
    assert income.kind == KIND_NONE


def test_fully_unemployed_month():
    line = IncomeTimeline(
        periods=(
            period((2026, 1, 1), (2026, 3, 31), "100000"),
            period((2026, 4, 1), (2026, 4, 30), unemployed=True),
            period((2026, 5, 1), None, "100000"),
        ),
        average_wage=Decimal("87000"),
    )
    income = line.income_for_month(2026, 4)
    assert income.amount == Decimal("87000.00")
    assert income.kind == KIND_UNEMPLOYED
    assert income.unemployed_days == 30


def test_single_day_gap():
    """Один день без заработка из 31 — 1/31 средней вместо 1/31 зарплаты."""
    line = IncomeTimeline(
        periods=(
            period((2026, 1, 1), (2026, 1, 14), "310000"),
            period((2026, 1, 15), (2026, 1, 15), unemployed=True),
            period((2026, 1, 16), None, "310000"),
        ),
        average_wage=Decimal("93000"),
    )
    income = line.income_for_month(2026, 1)
    assert income.unemployed_days == 1
    # 310000*30/31 + 93000*1/31
    assert income.amount == Decimal("303000.00")


def test_leap_february():
    line = IncomeTimeline(
        periods=(
            period((2024, 2, 1), (2024, 2, 29), "290000"),
            period((2024, 3, 1), None, "100000"),
        )
    )
    assert line.income_for_month(2024, 2).amount == Decimal("290000.00")


def test_gap_across_month_boundary(timeline):
    """Отрезок без заработка, накрывающий стык месяцев, делится между ними."""
    line = IncomeTimeline(
        periods=(
            period((2026, 1, 1), (2026, 3, 20), "300000"),
            period((2026, 3, 21), (2026, 4, 10), unemployed=True),
            period((2026, 4, 11), None, "300000"),
        ),
        average_wage=Decimal("90000"),
    )
    assert line.income_for_month(2026, 3).unemployed_days == 11
    assert line.income_for_month(2026, 4).unemployed_days == 10


def test_actual_income_overrides_periods(timeline):
    line = IncomeTimeline(
        periods=timeline.periods,
        average_wage=timeline.average_wage,
        actual=(((2026, 4), Decimal("152300.00")),),
    )
    income = line.income_for_month(2026, 4)
    assert income.amount == Decimal("152300.00")
    assert income.kind == KIND_ACTUAL
    assert income.unemployed_days == 0
    # Соседние месяцы считаются по периодам.
    assert line.income_for_month(2026, 3).amount == Decimal("140000.00")


def test_income_on_uses_the_month_of_the_date(timeline):
    assert timeline.income_on(datetime.date(2026, 4, 15)) == Decimal("108133.33")
    assert timeline.income_on(datetime.date(2026, 3, 15)) == Decimal("140000.00")


def test_start_is_the_first_period(timeline):
    assert timeline.start == datetime.date(2024, 9, 1)


def test_single_period_helper():
    line = single_period(Decimal("100000"), datetime.date(2026, 1, 1))
    assert line.start == datetime.date(2026, 1, 1)
    assert line.income_for_month(2026, 6).amount == Decimal("100000.00")
    assert line.income_for_month(2025, 12).kind == KIND_NONE


def test_unemployed_without_average_wage_yields_zero():
    """Валидация конфига такого не пропустит, но модель не должна падать."""
    line = IncomeTimeline(periods=(period((2026, 1, 1), None, unemployed=True),))
    assert line.income_for_month(2026, 1).amount == Decimal("0.00")


def test_period_unemployed_flag():
    assert period((2026, 1, 1), None, unemployed=True).unemployed is True
    assert period((2026, 1, 1), None, "1").unemployed is False
