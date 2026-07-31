"""
Отрисовка результата: человекочитаемый отчёт и JSON.
"""

import json
import textwrap
from decimal import Decimal

from pyalimony.struct import Calculation, Child
from pyalimony.utils import ZERO, format_date, format_money, format_percent, plural

_LABEL_WIDTH = 42
_WRAP_WIDTH = 100


def _row(label: str, value: str, indent: int = 0) -> str:
    pad = " " * indent
    return f"{pad}{label:<{_LABEL_WIDTH - indent}}{value:>18}\n"


def render_summary(calc: Calculation) -> str:
    """
    Шапка отчёта: доход и удержания.

    :param calc: результат расчёта
    :return: текстовый блок
    """
    out = f"Расчёт на {format_date(calc.as_of)}\n\n"
    out += _row("Чистый доход в месяц (после НДФЛ):", format_money(calc.net_income))
    out += _row(
        f"Удержания по алиментным ИП ({format_percent(calc.alimony_percent)}):",
        format_money(calc.alimony_withheld),
    )
    if calc.other_withholding_percent > ZERO:
        out += _row(
            f"Прочие удержания ({format_percent(calc.other_withholding_percent)}):",
            format_money(calc.other_withheld),
        )
    out += _row(
        f"Итого удержано ({format_percent(calc.total_withheld_percent)}):",
        format_money(calc.total_withheld),
    )
    out += _row("Остаётся на руки:", format_money(calc.take_home))
    out += _row("Предел удержания (ст. 99 ФЗ-229):", format_percent(calc.withholding_limit))
    return out


def render_status(child: Child) -> str:
    """
    Краткий статус ребёнка и его алиментного обязательства.

    :param child: посчитанный ребёнок
    :return: строка статуса
    """
    if child.is_closed:
        return "производство прекращено"
    years = f"{child.age} {plural(child.age, 'год', 'года', 'лет')}"
    end = child.obligation_end
    if end is None:
        return f"{years}, нетрудоспособный — обязательство бессрочно (ст. 85 СК РФ)"
    if child.obligation_active:
        if child.ended_early:
            return f"{years}, обязательство действует до {format_date(end)}"
        return f"{years}, несовершеннолетний до {format_date(end)}"
    if child.ended_early:
        return f"{years}, обязательство прекращено досрочно {format_date(end)}"
    return f"{years}, совершеннолетний с {format_date(end)}"


def render_child(child: Child) -> str:
    """
    Блок по одному исполнительному производству.

    :param child: посчитанный ребёнок
    :return: текстовый блок
    """
    out = f"\n{child.full_name}, {format_date(child.birthday)} г.р. — {render_status(child)}\n"
    if child.is_closed:
        return out

    if child.obligation_active:
        basis = "ст. 83 СК РФ" if child.config.alimony.is_fixed else "ст. 81 СК РФ"
        if child.config.disabled and not child.is_minor:
            basis = "ст. 85 СК РФ"
        out += _row(f"Текущий платёж ({basis}):", format_money(child.alimony_amount), indent=2)
    else:
        out += _row("Текущий платёж:", "прекращён (ст. 120 СК РФ)", indent=2)

    out += _row("В счёт задолженности:", format_money(child.debt_payment), indent=2)
    out += _row(
        f"Всего по ИП ({format_percent(child.total_percent)}):",
        format_money(child.total_payment),
        indent=2,
    )
    if child.initial_debt > ZERO:
        out += _row(
            f"Задолженность на {format_date(child.debt_as_of)}:",
            format_money(child.initial_debt),
            indent=2,
        )
        out += _row("Остаток на расчётную дату:", format_money(child.current_debt), indent=2)

    months_left = child.months_left
    if child.current_debt <= ZERO:
        out += _row("Погашение:", "задолженности нет", indent=2)
    elif months_left is None:
        out += _row("Погашение:", "не гасится", indent=2)
    else:
        payoff = child.payoff_date
        tail = f" (к {format_date(payoff)})" if payoff else ""
        word = plural(months_left, "месяц", "месяца", "месяцев")
        out += _row("Погашение:", f"{months_left} {word}{tail}", indent=2)
    return out


def render_warnings(calc: Calculation) -> str:
    """
    Блок предупреждений о расхождениях с нормами.

    :param calc: результат расчёта
    :return: текстовый блок, пустой если замечаний нет
    """
    if not calc.warnings:
        return ""
    out = "\nЗамечания:\n"
    for note in calc.warnings:
        out += textwrap.fill(note, width=_WRAP_WIDTH, initial_indent="  ! ", subsequent_indent="    ") + "\n"
    return out


def report(calc: Calculation) -> str:
    """
    Полный текстовый отчёт.

    :param calc: результат расчёта
    :return: готовый к печати текст
    """
    body = render_summary(calc)
    for child in calc.children:
        body += render_child(child)
    if calc.children:
        body += "\n"
        body += _row("Суммарный остаток задолженности:", format_money(calc.total_debt))
    return body + render_warnings(calc)


def as_dict(calc: Calculation) -> dict:
    """
    Представление результата для машинной обработки.

    :param calc: результат расчёта
    :return: словарь с примитивными типами
    """
    return {
        "as_of": calc.as_of.isoformat(),
        "net_income": _num(calc.net_income),
        "alimony_percent": _num(calc.alimony_percent),
        "alimony_withheld": _num(calc.alimony_withheld),
        "other_withholding_percent": _num(calc.other_withholding_percent),
        "other_withheld": _num(calc.other_withheld),
        "total_withheld_percent": _num(calc.total_withheld_percent),
        "total_withheld": _num(calc.total_withheld),
        "take_home": _num(calc.take_home),
        "withholding_limit": _num(calc.withholding_limit),
        "total_debt": _num(calc.total_debt),
        "children": [_child_dict(child) for child in calc.children],
        "warnings": list(calc.warnings),
    }


def _child_dict(child: Child) -> dict:
    payoff = child.payoff_date
    return {
        "full_name": child.full_name,
        "birthday": child.birthday.isoformat(),
        "majority_date": child.majority_date.isoformat(),
        "obligation_end": child.obligation_end.isoformat() if child.obligation_end else None,
        "obligation_active": child.obligation_active,
        "ended_early": child.ended_early,
        "disabled": child.config.disabled,
        "closed": child.is_closed,
        "age": child.age,
        "is_minor": child.is_minor,
        "total_percent": _num(child.total_percent),
        "total_payment": _num(child.total_payment),
        "alimony_amount": _num(child.alimony_amount),
        "debt_payment": _num(child.debt_payment),
        "initial_debt": _num(child.initial_debt),
        "debt_as_of": child.debt_as_of.isoformat(),
        "current_debt": _num(child.current_debt),
        "months_left": child.months_left,
        "payoff_date": payoff.isoformat() if payoff else None,
        "is_closable": child.is_closable,
    }


def _num(value: Decimal) -> float:
    return float(value)


def render_json(calc: Calculation) -> str:
    """
    Результат в JSON.

    :param calc: результат расчёта
    :return: JSON-строка
    """
    return json.dumps(as_dict(calc), ensure_ascii=False, indent=2)
