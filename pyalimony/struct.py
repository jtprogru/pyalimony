"""
Ключевые классы структур данных
"""

import datetime

from pyalimony.config import SALARY
from pyalimony.utils import get_percent_of_salary


class Children:
    """
    Класс описывающий ребенка с алиментами
    """

    def __init__(self, first_name: str, second_name: str, middle_name: str, birthday: str, alimony: dict):
        self.first_name = first_name
        self.second_name = second_name
        self.middle_name = middle_name
        self.birthday = birthday
        self.alimony = alimony
        # Задолженность
        self.debt = self.alimony["debt"]
        # Размер назначенных алиментов
        self.alimony_percent = self.alimony["alimony_percent"]
        # Суммарный процент с учетом долга
        self.total_percent = self.alimony["total_percent"]
        # С какого месяца задолженность
        self.start_month = 3
        # Суммарный платёж
        self.total_payment = round(get_percent_of_salary(amount=SALARY, percentile=self.total_percent), 2)
        # Платеж по алиментам
        self.alimony_amount = round(get_percent_of_salary(amount=SALARY, percentile=self.alimony_percent), 2)
        # Платеж по задолженности
        self.debt_payment = round(self.total_payment - self.alimony_amount, 2)
        # Сколько всего месяцев выплачивать задолженность
        self.total_how_long = round(self.debt / self.debt_payment, 2)
        # Сколько осталось месяцев выплачивать задолженность
        self.last_how_long = round(self.current_debt() / self.debt_payment, 2)

    def current_debt(self):
        cur_month = datetime.date.today().month
        return round(self.debt - (self.debt_payment * (cur_month - self.start_month - 1)), 2)

    def __repr__(self):
        return f"ФИО:\t{self.first_name} {self.second_name}\t{self.birthday} г.р."
