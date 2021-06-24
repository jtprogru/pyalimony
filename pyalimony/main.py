#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Author: Michael Savin <mail@jtprog.ru>
# WWW: https://jtprog.ru
"""
    В общих чертах описание текстом
    сумма зарплаты минус 70 процентов = то что я получаю
    40 процентов идут в счет первого ребенка
        из них 25 = текущий платеж
        а 15 = погашение долга
    30 процентов идут в счет второго ребенка
        из них 16.6 = текущий платеж
        а 13.7 = погашение долга
"""

from pyalimony.struct import Children, AlimonyChildren
from pyalimony.reports import report


def main():
    children1 = Children(
        first_name='Савина',
        second_name='Анна',
        middle_name='Михайловна',
        birthday='08.11.2016',
        alimony=AlimonyChildren(
            total_percent=40.0,
            alimony_percent=25.0,
            debt=280762.28
        )
    )

    children2 = Children(
        first_name='Савин',
        second_name='Артём',
        middle_name='Михайлович',
        birthday='30.05.2019',
        alimony=AlimonyChildren(
            total_percent=30.0,
            alimony_percent=16.6,
            debt=140885.13
        )
    )

    print(report([children1,
                 children2]))


if __name__ == '__main__':
    main()
