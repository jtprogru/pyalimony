# -*- coding: utf-8 -*-
"""
    Базовые параметры
"""
import os

from ruamel.yaml import YAML, YAMLError

yaml = YAML(typ='safe', pure=True)

CHILDRENS = []

HOME = os.getenv("HOME", None)

CONFIG_FILE = f"{HOME}/.config/alimony.yaml"

with open(CONFIG_FILE, 'r') as stream:
    try:
        data = yaml.load(stream)
        CHILDRENS.extend(data['childrens'])
        SALARY = data['SALARY']
        # Рразмер удержаний по всем ИП
        PERCENT = data['PERCENT']
    except YAMLError as exc:
        print(exc)
