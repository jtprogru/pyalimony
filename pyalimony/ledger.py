"""
Помесячная выгрузка: что начислено и удержано по каждому ИП за каждый месяц.

Выгрузка целиком выводится из конфига, поэтому её можно удалить и построить
заново. Источник истины — конфиг, CSV нужен для просмотра глазами, выгрузки
в таблицу и построения HTML-отчёта.
"""

import calendar
import csv
import datetime
from dataclasses import dataclass, fields
from decimal import Decimal
from pathlib import Path

from pyalimony.config import Config
from pyalimony.struct import Child
from pyalimony.utils import ZERO, quantize_money

CSV_COLUMNS = (
    "month",
    "child",
    "income",
    "income_kind",
    "unemployed_days",
    "alimony",
    "debt_payment",
    "total",
    "debt_left",
)


@dataclass(frozen=True, slots=True)
class LedgerRow:
    """
    Одна строка выгрузки: один ребёнок за один месяц.

    :param month: первое число месяца
    :param child: ФИО ребёнка
    :param income: доход, от которого считались алименты в этом месяце
    :param income_kind: происхождение дохода — зарплата, средняя, смешанно, факт
    :param unemployed_days: сколько дней месяца пришлось на период без заработка
    :param alimony: текущий платёж по алиментам
    :param debt_payment: удержание в счёт задолженности
    :param total: всё удержание по этому ИП за месяц
    :param debt_left: остаток задолженности на конец месяца; ``None`` для месяцев
        раньше даты постановления пристава, когда остаток неизвестен
    """

    month: datetime.date
    child: str
    income: Decimal
    income_kind: str
    unemployed_days: int
    alimony: Decimal
    debt_payment: Decimal
    total: Decimal
    debt_left: Decimal | None


def month_range(start: datetime.date, end: datetime.date) -> list[datetime.date]:
    """
    Список первых чисел месяцев от начала до конца включительно.

    :param start: любая дата первого месяца
    :param end: любая дата последнего месяца
    :return: список дат вида 1-е число
    """
    months = []
    current = start.replace(day=1)
    last = end.replace(day=1)
    while current <= last:
        months.append(current)
        year, month = divmod(current.month, 12)
        current = datetime.date(current.year + year, month + 1, 1)
    return months


def end_of_month(day: datetime.date) -> datetime.date:
    """
    Последний день месяца.

    :param day: любая дата месяца
    :return: дата последнего дня
    """
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def build_ledger(config: Config, as_of: datetime.date | None = None) -> tuple[LedgerRow, ...]:
    """
    Построить помесячную выгрузку по всем исполнительным производствам.

    Каждый месяц считается отдельно: доход берётся из истории с точностью до дня,
    ставка — с учётом того, действовало ли обязательство в этом месяце.

    :param config: разобранный конфиг
    :param as_of: последний месяц выгрузки, по умолчанию текущий
    :return: строки, отсортированные по месяцу и ребёнку
    """
    end = as_of or datetime.date.today()
    rows: list[LedgerRow] = []

    for child_config in config.children:
        if child_config.alimony.closed:
            continue
        anchor = Child(config=child_config, income=config.income, as_of=end)
        start = max(anchor.started_at, config.income.start or anchor.started_at)
        if start > end:
            continue
        for month in month_range(start, end):
            rows.append(_row_for_month(child_config, config, month, end))

    rows.sort(key=lambda row: (row.month, row.child))
    return tuple(rows)


def _row_for_month(child_config, config: Config, month: datetime.date, horizon: datetime.date) -> LedgerRow:
    """Посчитать одну строку выгрузки."""
    closing = min(end_of_month(month), horizon)
    child = Child(config=child_config, income=config.income, as_of=closing)
    month_income = config.income.income_for_month(month.year, month.month)

    alimony = child.alimony_on(month)
    debt_payment = child.debt_payment_on(month)
    debt_left = child.current_debt if closing >= child.debt_as_of else None

    return LedgerRow(
        month=month,
        child=child.full_name,
        income=month_income.amount,
        income_kind=month_income.kind,
        unemployed_days=month_income.unemployed_days,
        alimony=alimony,
        debt_payment=debt_payment,
        total=quantize_money(alimony + debt_payment),
        debt_left=debt_left,
    )


def write_csv(rows: tuple[LedgerRow, ...], path: Path) -> Path:
    """
    Записать выгрузку в CSV, создав каталог при необходимости.

    :param rows: строки выгрузки
    :param path: путь к файлу
    :return: путь к записанному файлу
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(CSV_COLUMNS)
        for row in rows:
            writer.writerow(
                [
                    f"{row.month:%Y-%m}",
                    row.child,
                    row.income,
                    row.income_kind,
                    row.unemployed_days,
                    row.alimony,
                    row.debt_payment,
                    row.total,
                    "" if row.debt_left is None else row.debt_left,
                ]
            )
    return path


def read_csv(path: Path) -> tuple[LedgerRow, ...]:
    """
    Прочитать выгрузку из CSV.

    :param path: путь к файлу
    :return: строки выгрузки
    """
    with path.open(encoding="utf-8", newline="") as stream:
        rows = []
        for record in csv.DictReader(stream):
            year, month = (int(part) for part in record["month"].split("-"))
            rows.append(
                LedgerRow(
                    month=datetime.date(year, month, 1),
                    child=record["child"],
                    income=Decimal(record["income"]),
                    income_kind=record["income_kind"],
                    unemployed_days=int(record["unemployed_days"]),
                    alimony=Decimal(record["alimony"]),
                    debt_payment=Decimal(record["debt_payment"]),
                    total=Decimal(record["total"]),
                    debt_left=Decimal(record["debt_left"]) if record["debt_left"] else None,
                )
            )
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class Totals:
    """Свод по группе строк."""

    alimony: Decimal = ZERO
    debt_payment: Decimal = ZERO
    total: Decimal = ZERO

    def plus(self, row: LedgerRow) -> Totals:
        """
        Прибавить строку выгрузки.

        :param row: строка
        :return: новый свод
        """
        return Totals(
            alimony=quantize_money(self.alimony + row.alimony),
            debt_payment=quantize_money(self.debt_payment + row.debt_payment),
            total=quantize_money(self.total + row.total),
        )


def sum_rows(rows: tuple[LedgerRow, ...]) -> Totals:
    """
    Свести строки в одну сумму.

    :param rows: строки выгрузки
    :return: свод
    """
    totals = Totals()
    for row in rows:
        totals = totals.plus(row)
    return totals


def group_by_year(rows: tuple[LedgerRow, ...]) -> dict[int, tuple[LedgerRow, ...]]:
    """
    Сгруппировать строки по годам.

    :param rows: строки выгрузки
    :return: год → строки
    """
    grouped: dict[int, list[LedgerRow]] = {}
    for row in rows:
        grouped.setdefault(row.month.year, []).append(row)
    return {year: tuple(items) for year, items in sorted(grouped.items())}


def children_names(rows: tuple[LedgerRow, ...]) -> tuple[str, ...]:
    """
    Имена детей в порядке первого появления.

    :param rows: строки выгрузки
    :return: кортеж ФИО
    """
    seen: dict[str, None] = {}
    for row in rows:
        seen.setdefault(row.child, None)
    return tuple(seen)


def column_names() -> tuple[str, ...]:
    """
    Имена полей строки выгрузки.

    :return: кортеж имён
    """
    return tuple(item.name for item in fields(LedgerRow))
