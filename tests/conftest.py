"""
Общая инфраструктура тестов.

Пакет больше не читает конфиг на этапе импорта, поэтому перезагрузки модулей
не нужны: конфиг пишется во временный файл либо разбирается прямо из строки.
"""

import datetime
import textwrap
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from pyalimony.config import load_config, parse_config
from pyalimony.struct import calculate

_yaml = YAML(typ="safe", pure=True)

# Опорная дата всех расчётов: старший ребёнок уже совершеннолетний, младший — нет.
TODAY = datetime.date(2026, 7, 31)

# Базовый конфиг подобран так, чтобы не порождать замечаний, кроме напоминания
# о неустойке: 70 % укладываются в предел, доля по несовершеннолетнему равна 1/4.
BASE_CONFIG = """---
net_income: 100000
other_withholding_percent: 0.0

children:
  - surname: 'Иванов'
    name: 'Иван'
    patronymic: 'Иванович'
    birthday: '30.11.2006'
    alimony:
      total_percent: 40.0
      alimony_percent: 25.0
      debt: 200000
      debt_as_of: '01.03.2026'

  - surname: 'Петров'
    name: 'Пётр'
    patronymic: 'Петрович'
    birthday: '08.05.2015'
    alimony:
      total_percent: 30.0
      alimony_percent: 25.0
      debt: 100000
      debt_as_of: '01.03.2026'
"""

MINOR_ONLY_CONFIG = """---
net_income: 100000

children:
  - surname: 'Сидоров'
    name: 'Сидор'
    patronymic: 'Сидорович'
    birthday: '01.01.2015'
    alimony:
      total_percent: 40.0
      alimony_percent: 25.0
      debt: 60000
      debt_as_of: '01.03.2026'
"""


CLOSED_CONFIG = """
    ---
    net_income: 100000
    children:
      - surname: 'Первый'
        name: 'Ребёнок'
        birthday: '01.01.2000'
        alimony:
          closed: true
      - surname: 'Второй'
        name: 'Ребёнок'
        birthday: '01.01.2015'
        alimony:
          total_percent: 25.0
          alimony_percent: 25.0
    """

DISABLED_CONFIG = """
    ---
    net_income: 100000
    children:
      - surname: 'Иванов'
        name: 'Иван'
        birthday: '01.01.2000'
        disabled: true
        alimony:
          total_percent: 20.0
          alimony_fixed: 20000
    """

EMANCIPATED_CONFIG = """
    ---
    net_income: 100000
    children:
      - surname: 'Иванов'
        name: 'Иван'
        birthday: '01.06.2010'
        obligation_ended: '01.03.2026'
        alimony:
          total_percent: 40.0
          alimony_percent: 25.0
          debt: 100000
          debt_as_of: '01.01.2026'
    """


@pytest.fixture
def write_config(tmp_path):
    """Записать YAML во временный файл и вернуть путь."""

    def _write(text: str, name: str = "alimony.yaml") -> Path:
        path = tmp_path / name
        path.write_text(textwrap.dedent(text), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def config_from_text():
    """Разобрать YAML-текст в Config, минуя файловую систему."""

    def _parse(text: str = BASE_CONFIG):
        return parse_config(_yaml.load(textwrap.dedent(text)))

    return _parse


@pytest.fixture
def calc(config_from_text):
    """Посчитать конфиг на опорную дату."""

    def _calc(text: str = BASE_CONFIG, as_of: datetime.date = TODAY):
        return calculate(config_from_text(text), as_of=as_of)

    return _calc


@pytest.fixture
def load(write_config):
    """Прогнать конфиг через полный путь: файл → load_config."""

    def _load(text: str):
        return load_config(write_config(text))

    return _load
