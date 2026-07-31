"""Тесты помесячной выгрузки."""

import datetime
from decimal import Decimal

import pytest

from pyalimony.ledger import (
    CSV_COLUMNS,
    build_ledger,
    children_names,
    column_names,
    end_of_month,
    group_by_year,
    month_range,
    read_csv,
    sum_rows,
    write_csv,
)
from tests.conftest import BASE_CONFIG, CLOSED_CONFIG, HISTORY_CONFIG, TODAY


@pytest.fixture
def rows(config_from_text):
    return build_ledger(config_from_text(HISTORY_CONFIG), as_of=TODAY)


def test_month_range_inclusive():
    months = month_range(datetime.date(2025, 11, 20), datetime.date(2026, 2, 3))
    assert months == [
        datetime.date(2025, 11, 1),
        datetime.date(2025, 12, 1),
        datetime.date(2026, 1, 1),
        datetime.date(2026, 2, 1),
    ]


def test_month_range_single_month():
    assert month_range(datetime.date(2026, 4, 5), datetime.date(2026, 4, 30)) == [datetime.date(2026, 4, 1)]


@pytest.mark.parametrize(
    ("day", "expected"),
    [((2026, 4, 1), (2026, 4, 30)), ((2026, 2, 10), (2026, 2, 28)), ((2024, 2, 1), (2024, 2, 29))],
)
def test_end_of_month(day, expected):
    assert end_of_month(datetime.date(*day)) == datetime.date(*expected)


def test_ledger_covers_every_month(rows):
    months = sorted({row.month for row in rows})
    assert months[0] == datetime.date(2025, 10, 1)
    assert months[-1] == datetime.date(2026, 7, 1)
    assert len(months) == 10


def test_ledger_has_a_row_per_child_per_month(rows):
    assert len(rows) == 10 * 2
    assert children_names(rows) == ("Иванов Иван Иванович", "Петров Пётр Петрович")


def test_rows_are_sorted_by_month_then_child(rows):
    keys = [(row.month, row.child) for row in rows]
    assert keys == sorted(keys)


def test_full_salary_month(rows):
    row = next(r for r in rows if r.month == datetime.date(2026, 3, 1) and r.child.startswith("Иванов"))
    assert row.income == Decimal("140000.00")
    assert row.income_kind == "salary"
    assert row.unemployed_days == 0
    assert row.total == Decimal("56000.00")  # 40 % от 140000


def test_split_month_uses_average_wage(rows):
    """Апрель: 5 дней по 140000, 22 дня по средней 87000, 3 дня по 210000."""
    row = next(r for r in rows if r.month == datetime.date(2026, 4, 1) and r.child.startswith("Иванов"))
    assert row.income == Decimal("108133.33")
    assert row.income_kind == "mixed"
    assert row.unemployed_days == 22
    assert row.total == Decimal("43253.33")


def test_month_after_the_gap(rows):
    row = next(r for r in rows if r.month == datetime.date(2026, 5, 1) and r.child.startswith("Иванов"))
    assert row.income == Decimal("210000.00")
    assert row.income_kind == "salary"


def test_alimony_and_debt_add_up(rows):
    for row in rows:
        assert row.alimony + row.debt_payment == row.total


def test_debt_left_is_empty_before_the_snapshot(rows):
    early = [r for r in rows if r.month < datetime.date(2026, 3, 1)]
    assert early
    assert all(row.debt_left is None for row in early)


def test_debt_left_is_filled_from_the_snapshot(rows):
    later = [r for r in rows if r.month >= datetime.date(2026, 3, 1)]
    assert all(row.debt_left is not None for row in later)


def test_debt_left_never_grows(rows):
    for name in children_names(rows):
        history = [r.debt_left for r in rows if r.child == name and r.debt_left is not None]
        assert history == sorted(history, reverse=True)


def test_current_alimony_stops_at_majority(rows):
    """Иванов совершеннолетний с 30.11.2024 — текущего платежа быть не должно."""
    ivanov = [r for r in rows if r.child.startswith("Иванов")]
    assert all(row.alimony == Decimal("0.00") for row in ivanov)
    assert all(row.debt_payment == row.total for row in ivanov)


def test_closed_order_is_absent(config_from_text):
    rows = build_ledger(config_from_text(CLOSED_CONFIG), as_of=TODAY)
    assert all(not row.child.startswith("Первый") for row in rows)
    assert children_names(rows) == ("Второй Ребёнок",)


def test_scalar_income_starts_at_the_debt_snapshot(config_from_text):
    """Без истории дохода отсчёт ведётся от постановления пристава."""
    rows = build_ledger(config_from_text(BASE_CONFIG), as_of=TODAY)
    assert min(row.month for row in rows) == datetime.date(2026, 3, 1)


def test_ledger_defaults_to_today(config_from_text):
    rows = build_ledger(config_from_text(BASE_CONFIG))
    assert max(row.month for row in rows) == datetime.date.today().replace(day=1)


def test_order_start_date_limits_the_ledger(config_from_text):
    config = HISTORY_CONFIG.replace("started_at: '01.10.2025'", "started_at: '01.02.2026'")
    rows = build_ledger(config_from_text(config), as_of=TODAY)
    ivanov = [r for r in rows if r.child.startswith("Иванов")]
    assert min(row.month for row in ivanov) == datetime.date(2026, 2, 1)


def test_order_starting_after_horizon_is_skipped(config_from_text):
    config = HISTORY_CONFIG.replace("started_at: '01.10.2025'", "started_at: '01.07.2026'")
    rows = build_ledger(config_from_text(config), as_of=datetime.date(2026, 6, 30))
    assert all(not row.child.startswith("Иванов") for row in rows)


def test_sum_rows(rows):
    totals = sum_rows(rows)
    assert totals.alimony + totals.debt_payment == totals.total
    assert totals.total == sum((row.total for row in rows), start=Decimal("0"))


def test_sum_of_empty_is_zero():
    totals = sum_rows(())
    assert (totals.alimony, totals.debt_payment, totals.total) == (Decimal("0"),) * 3


def test_group_by_year(rows):
    grouped = group_by_year(rows)
    assert list(grouped) == [2025, 2026]
    assert len(grouped[2025]) == 3 * 2
    assert len(grouped[2026]) == 7 * 2


def test_column_names_match_csv_header():
    assert column_names() == CSV_COLUMNS


def test_csv_roundtrip(rows, tmp_path):
    path = write_csv(rows, tmp_path / "nested" / "ledger.csv")
    assert path.exists()
    assert read_csv(path) == rows


def test_csv_has_a_header(rows, tmp_path):
    path = write_csv(rows, tmp_path / "ledger.csv")
    assert path.read_text(encoding="utf-8").splitlines()[0] == ",".join(CSV_COLUMNS)


def test_csv_leaves_unknown_debt_empty(rows, tmp_path):
    path = write_csv(rows, tmp_path / "ledger.csv")
    line = next(row for row in path.read_text(encoding="utf-8").splitlines() if row.startswith("2025-10"))
    assert line.endswith(",")


def test_csv_of_empty_ledger(tmp_path):
    path = write_csv((), tmp_path / "ledger.csv")
    assert read_csv(path) == ()
