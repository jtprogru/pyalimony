"""
Доход по периодам с точностью до дня.

Смена работодателя и перерывы между работами приходятся на середину месяца,
поэтому доход задаётся отрезками календарных дат, а не одним числом. Начисление
за месяц собирается из отрезков пропорционально календарным дням.

За дни без дохода применяется средняя заработная плата по РФ — так пристав
считает задолженность по п. 4 ст. 113 СК РФ, если человек не работал или не
представил документы о заработке.
"""

import calendar
import datetime
from dataclasses import dataclass
from decimal import Decimal

from pyalimony.utils import ZERO, quantize_money

# Виды месячного дохода — попадают в выгрузку и в отчёт.
KIND_SALARY = "salary"
KIND_UNEMPLOYED = "unemployed"
KIND_MIXED = "mixed"
KIND_ACTUAL = "actual"
KIND_NONE = "none"


@dataclass(frozen=True, slots=True)
class IncomePeriod:
    """
    Отрезок с постоянной месячной ставкой дохода.

    :param start: первый день отрезка; ``None`` — отрезок открыт в прошлое
    :param end: последний день; ``None`` — отрезок открыт до сегодняшнего дня
    :param net_monthly: месячный доход после НДФЛ; ``None`` — дохода не было
    """

    start: datetime.date | None
    end: datetime.date | None
    net_monthly: Decimal | None

    @property
    def unemployed(self) -> bool:
        """Отрезок без дохода."""
        return self.net_monthly is None


@dataclass(frozen=True, slots=True)
class MonthIncome:
    """
    Доход за конкретный месяц.

    :param amount: сумма, от которой считаются алименты за этот месяц
    :param kind: как она получена — из зарплаты, по средней, смешанно, фактом
    :param unemployed_days: сколько дней месяца пришлось на период без дохода
    """

    amount: Decimal
    kind: str
    unemployed_days: int = 0


@dataclass(frozen=True, slots=True)
class IncomeTimeline:
    """
    Полная история дохода.

    :param periods: отрезки, отсортированные, без пересечений и разрывов
    :param average_wage: средняя зарплата по РФ для дней без дохода (п. 4 ст. 113 СК РФ)
    :param actual: фактический доход за отдельные месяцы, ключ ``(год, месяц)`` —
        перекрывает расчёт по отрезкам
    """

    periods: tuple[IncomePeriod, ...]
    average_wage: Decimal | None = None
    actual: tuple[tuple[tuple[int, int], Decimal], ...] = ()

    @property
    def start(self) -> datetime.date | None:
        """
        Первый день, покрытый историей дохода.

        ``None`` — доход задан одним числом без даты начала, то есть считается
        постоянным за всё время.
        """
        return self.periods[0].start

    def _actual_for(self, year: int, month: int) -> Decimal | None:
        for (a_year, a_month), amount in self.actual:
            if (a_year, a_month) == (year, month):
                return amount
        return None

    def income_for_month(self, year: int, month: int) -> MonthIncome:
        """
        Собрать доход за месяц из отрезков.

        Каждый отрезок вносит свою месячную ставку пропорционально числу
        календарных дней, которые он занимает в этом месяце.

        :param year: год
        :param month: месяц
        :return: доход за месяц с пометкой о его происхождении
        """
        actual = self._actual_for(year, month)
        if actual is not None:
            return MonthIncome(amount=actual, kind=KIND_ACTUAL)

        days_in_month = calendar.monthrange(year, month)[1]
        first = datetime.date(year, month, 1)
        last = datetime.date(year, month, days_in_month)

        total = ZERO
        salary_days = 0
        unemployed_days = 0
        for period in self.periods:
            seg_start = first if period.start is None else max(period.start, first)
            seg_end = min(period.end or last, last)
            if seg_start > seg_end:
                continue
            days = (seg_end - seg_start).days + 1
            if period.unemployed:
                unemployed_days += days
                base = self.average_wage or ZERO
            else:
                salary_days += days
                base = period.net_monthly or ZERO
            total += base * Decimal(days) / Decimal(days_in_month)

        if salary_days == 0 and unemployed_days == 0:
            return MonthIncome(amount=ZERO, kind=KIND_NONE)
        if unemployed_days == 0:
            kind = KIND_SALARY
        elif salary_days == 0:
            kind = KIND_UNEMPLOYED
        else:
            kind = KIND_MIXED
        return MonthIncome(amount=quantize_money(total), kind=kind, unemployed_days=unemployed_days)

    def income_on(self, day: datetime.date) -> Decimal:
        """
        Доход за месяц, в который попадает дата.

        :param day: дата
        :return: сумма, от которой считаются алименты за этот месяц
        """
        return self.income_for_month(day.year, day.month).amount


def single_period(net_monthly: Decimal, start: datetime.date | None = None) -> IncomeTimeline:
    """
    Таймлайн из одного отрезка — простой случай постоянного дохода.

    Без даты начала отрезок открыт в обе стороны: доход считается постоянным
    за всё время, включая прошлые месяцы.

    :param net_monthly: месячный доход после НДФЛ
    :param start: с какой даты он известен; ``None`` — за всё время
    :return: таймлайн с единственным периодом
    """
    return IncomeTimeline(periods=(IncomePeriod(start=start, end=None, net_monthly=net_monthly),))
