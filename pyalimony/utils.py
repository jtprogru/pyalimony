# coding=utf-8

"""
    Утилиты и хелперы
"""


def get_percent_of_salary(amount: float, percentile: float) -> float:
    """
    :param amount: Размер зарплаты
    :param percentile: Количество процентов
    :return: количество денег равное количеству процентов от зарплаты
    """
    return (amount / 100) * percentile
