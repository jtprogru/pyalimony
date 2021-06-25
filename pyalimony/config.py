# -*- coding: utf-8 -*-
"""
    Базовые параметры
"""
from ruamel.yaml import YAML, YAMLError
from pprint import pprint

yaml = YAML(typ='safe', pure=True)

CHILDRENS = []

with open("config.yaml", 'r') as stream:
    try:
        data = yaml.load(stream)
        CHILDRENS.extend(data['childrens'])
        SALARY = data['SALARY']
        # Рразмер удержаний по всем ИП
        PERCENT = data['PERCENT']
        # pprint(CHILDRENS)
    except YAMLError as exc:
        print(exc)

# Размер зарплаты после вычета налогов
# SALARY = 230550.0
# Рразмер удержаний по всем ИП
# PERCENT = 70.0
