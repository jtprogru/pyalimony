"""
Утилиты: деньги, проценты, даты.

Деньги везде Decimal с округлением half-up до копеек: float даёт 11620.000000000002
на ровных 16,6 % от 70 000, а встроенный round() округляет по-банковски
(round(2.5) == 2), что расходится с бухгалтерской практикой.
"""

import calendar
import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from pyalimony.errors import ConfigError

KOPECK = Decimal("0.01")
HUNDRED = Decimal("100")
ZERO = Decimal("0.00")

DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d")


def to_decimal(value: object, field: str) -> Decimal:
    """
    Привести значение из конфига к Decimal без промежуточного float.

    :param value: число или строка из YAML
    :param field: имя поля — попадёт в текст ошибки
    :return: Decimal
    :raises ConfigError: значение не число
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ConfigError(f"{field}: ожидалось число, получено {value!r}")
    try:
        return Decimal(str(value).strip().replace(",", "."))
    except InvalidOperation as exc:
        raise ConfigError(f"{field}: {value!r} не является числом") from exc


def to_money(value: object, field: str) -> Decimal:
    """
    Привести значение к денежной сумме, округлённой до копеек.

    :param value: число или строка из YAML
    :param field: имя поля — попадёт в текст ошибки
    :return: сумма в рублях с точностью до копейки
    """
    return quantize_money(to_decimal(value, field))


def quantize_money(value: Decimal) -> Decimal:
    """
    Округлить сумму до копеек по правилам арифметики (half-up).

    :param value: сумма
    :return: сумма, округлённая до двух знаков
    """
    return value.quantize(KOPECK, rounding=ROUND_HALF_UP)


def percent_of(amount: Decimal, percent: Decimal) -> Decimal:
    """
    Процент от суммы.

    :param amount: сумма
    :param percent: количество процентов
    :return: сумма, округлённая до копеек
    """
    return quantize_money(amount * percent / HUNDRED)


def parse_date(value: object, field: str) -> datetime.date:
    """
    Разобрать дату из конфига.

    Принимает ``ДД.ММ.ГГГГ``, ``ГГГГ-ММ-ДД`` и нативную дату YAML.

    :param value: значение из конфига
    :param field: имя поля — попадёт в текст ошибки
    :return: дата
    :raises ConfigError: дату не удалось разобрать
    """
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        for fmt in DATE_FORMATS:
            try:
                return datetime.datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    raise ConfigError(f"{field}: не удалось разобрать дату {value!r}, ожидается ДД.ММ.ГГГГ")


def add_months(day: datetime.date, months: int) -> datetime.date:
    """
    Прибавить месяцы к дате, не выходя за границы месяца.

    31 января плюс один месяц — 28 (или 29) февраля.

    :param day: исходная дата
    :param months: сколько месяцев прибавить, может быть отрицательным
    :return: новая дата
    """
    total = day.month - 1 + months
    year = day.year + total // 12
    month = total % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, min(day.day, last_day))


def full_months_between(start: datetime.date, end: datetime.date) -> int:
    """
    Количество полных месяцев между датами.

    Именно столько ежемесячных удержаний прошло с даты начала.

    :param start: начальная дата
    :param end: конечная дата
    :return: количество полных месяцев, не меньше нуля
    """
    if end <= start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(0, months)


def format_money(value: Decimal) -> str:
    """
    Отформатировать сумму с разделителями разрядов.

    :param value: сумма
    :return: строка вида ``1 234 567.89``
    """
    return f"{quantize_money(value):,.2f}".replace(",", " ")


def format_percent(value: Decimal) -> str:
    """
    Отформатировать процент.

    :param value: количество процентов
    :return: строка вида ``33.33 %``
    """
    return f"{value.quantize(KOPECK, rounding=ROUND_HALF_UP):.2f} %"


def plural(count: int, one: str, few: str, many: str) -> str:
    """
    Выбрать форму слова по числу.

    :param count: число
    :param one: форма для 1 (месяц, ребёнка)
    :param few: форма для 2-4 (месяца, детей)
    :param many: форма для 0 и 5+ (месяцев, детей)
    :return: подходящая форма
    """
    tail_two = abs(count) % 100
    tail_one = abs(count) % 10
    if 11 <= tail_two <= 14 or tail_one == 0 or tail_one >= 5:
        return many
    return one if tail_one == 1 else few


def format_date(value: datetime.date) -> str:
    """
    Отформатировать дату в привычном виде.

    :param value: дата
    :return: строка вида ``30.11.2006``
    """
    return value.strftime("%d.%m.%Y")
