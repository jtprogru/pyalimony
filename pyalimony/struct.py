# coding=utf-8

import datetime

from pyalimony.config import SALARY
from pyalimony.utils import get_percent_of_salary


class AlimonyChildren:
    def __init__(self,
                 debt: float,
                 alimony_percent: float,
                 total_percent: float):
        # Задолженность
        self.debt = debt
        # Размер назначенных алиментов
        self.alimony_percent = alimony_percent
        # Суммарный процент с учетом долга
        self.total_percent = total_percent
        # С какого месяца задолженность
        self.start_month = 3
        # Суммарный платёж
        self.total_payment = float("{:10.2f}".format(get_percent_of_salary(amount=SALARY,
                                                                           percentile=self.total_percent)))
        # Платеж по алиментам
        self.alimony_amount = float("{:10.2f}".format(get_percent_of_salary(amount=SALARY,
                                                                            percentile=self.alimony_percent)))
        # Платеж по задолженности
        self.debt_payment = float("{:10.2f}".format(self.total_payment - self.alimony_amount))
        # Сколько всего месяцев выплачивать задолженность
        self.total_how_long = float("{:10.2f}".format(self.debt / self.debt_payment))
        # Сколько осталось месяцев выплачивать задолженность
        self.last_how_long = float("{:10.2f}".format(self.__current_debt() / self.debt_payment))

    def __current_debt(self):
        cur_month = datetime.date.today().month
        return float("{:10.2f}".format(self.debt - (self.debt_payment * (cur_month - self.start_month - 1))))


class Children:
    def __init__(self,
                 first_name: str,
                 second_name: str,
                 middle_name: str,
                 birthday: str,
                 alimony: AlimonyChildren):
        self.first_name = first_name
        self.second_name = second_name
        self.middle_name = middle_name
        self.birthday = birthday
        self.alimony = alimony

    def __repr__(self):
        return 'ФИО:\t{} {}\t{} г.р.'.format(self.first_name, self.second_name, self.birthday)
