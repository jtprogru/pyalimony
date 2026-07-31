"""Тесты нормативных констант и правил."""

import datetime
from decimal import Decimal

import pytest

from pyalimony import law


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, "0"), (1, "25"), (3, "50"), (5, "50"), (-1, "0")],
)
def test_statutory_share(count, expected):
    """п. 1 ст. 81 СК РФ: 1/4, 1/3, 1/2."""
    assert law.statutory_share(count) == Decimal(expected)


def test_statutory_share_for_two_children_is_one_third():
    share = law.statutory_share(2)
    assert share == Decimal("100") / Decimal("3")
    assert share.quantize(Decimal("0.01")) == Decimal("33.33")


@pytest.mark.parametrize(
    ("birthday", "expected"),
    [
        ((2006, 11, 30), (2024, 11, 30)),
        ((2015, 5, 8), (2033, 5, 8)),
        ((2000, 1, 1), (2018, 1, 1)),
    ],
)
def test_majority_date(birthday, expected):
    assert law.majority_date(datetime.date(*birthday)) == datetime.date(*expected)


def test_majority_date_for_leap_day():
    """29 февраля 2008 + 18 лет: в 2026 году февраль короткий."""
    assert law.majority_date(datetime.date(2008, 2, 29)) == datetime.date(2026, 2, 28)


@pytest.mark.parametrize(
    ("birthday", "on", "expected"),
    [
        ((2006, 11, 30), (2026, 7, 31), 19),
        ((2006, 11, 30), (2024, 11, 30), 18),
        ((2006, 11, 30), (2024, 11, 29), 17),
        ((2015, 5, 8), (2026, 7, 31), 11),
        ((2026, 7, 31), (2026, 7, 31), 0),
    ],
)
def test_age_on(birthday, on, expected):
    assert law.age_on(datetime.date(*birthday), datetime.date(*on)) == expected


def test_withholding_limit_with_minors():
    """ч. 3 ст. 99 ФЗ-229 — повышенный предел при алиментах на несовершеннолетних."""
    assert law.withholding_limit(has_minor_children=True) == Decimal("70")


def test_withholding_limit_without_minors():
    """ч. 2 ст. 99 ФЗ-229 — общий предел."""
    assert law.withholding_limit(has_minor_children=False) == Decimal("50")


def test_penalty_rates_match_statute():
    """п. 2 ст. 115 СК РФ: 0,1 % в день с 10.08.2018, до этого 0,5 %."""
    rates = (law.PENALTY_RATE_PER_DAY, law.PENALTY_RATE_PER_DAY_BEFORE, law.PENALTY_RATE_CHANGED_ON)
    assert rates == (Decimal("0.001"), Decimal("0.005"), datetime.date(2018, 8, 10))


def test_majority_age():
    assert law.MAJORITY_AGE == 18
