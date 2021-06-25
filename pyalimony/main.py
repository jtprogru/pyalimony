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

from pyalimony.struct import Children
from pyalimony.reports import report
from pyalimony.config import CHILDRENS


def main():
    child_list = []

    for ch in CHILDRENS:
        child_list.append(Children(**ch))
    print(report(child_list))


if __name__ == '__main__':
    main()
