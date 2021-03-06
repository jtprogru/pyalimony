# -*- coding: utf-8 -*-

"""
    Создание отчета
"""

from typing import List

from pyalimony.config import SALARY, PERCENT
from pyalimony.utils import get_percent_of_salary


def report(childrens: List) -> str:
    header = f"Текущая зарплата в месяц (чистыми):\t\t\t{SALARY}\n" + \
             f"Всего в месяц получу:\t\t\t\t\t{SALARY - get_percent_of_salary(amount=SALARY, percentile=PERCENT)}\n"
    month_total_amount = 'Каждому из детей в месяц будет выплачено (всего):\n'
    for ch in childrens:
        month_total_amount += f'\t{ch}:\t{ch.total_payment}\n'
    curr_amount = 'В счет текущих платежей будет выплачено:\n'
    for ch in childrens:
        curr_amount += f'\t{ch}:\t{ch.alimony_amount}\n'
    debt_amount = 'В счет погашения долга будет выплачено:\n'
    for ch in childrens:
        debt_amount += f'\t{ch}:\t{ch.debt_payment}\n'
    total_months = 'Сколько месяцев платить:\n'
    for ch in childrens:
        total_months += f'\t{ch}:\t{ch.total_how_long}\n'
    left_months = 'Сколько осталось месяцев платить:\n'
    for ch in childrens:
        left_months += f'\t{ch}:\t{ch.last_how_long}\n'
    curr_debt = 'Остаток на текущий месяц по долгу:\n'
    for ch in childrens:
        curr_debt += f'\t{ch}:\t{ch.current_debt()}\n'

    return header + month_total_amount + curr_amount + debt_amount + total_months + left_months + curr_debt
