"""
Базовые параметры
"""

from pathlib import Path

from ruamel.yaml import YAML, YAMLError

yaml = YAML(typ="safe", pure=True)

CHILDRENS = []

CONFIG_FILE = Path.home() / ".config" / "alimony.yaml"

with CONFIG_FILE.open() as stream:
    try:
        data = yaml.load(stream)
        CHILDRENS.extend(data["childrens"])
        SALARY = data["SALARY"]
        # Рразмер удержаний по всем ИП
        PERCENT = data["PERCENT"]
    except YAMLError as exc:
        print(exc)
