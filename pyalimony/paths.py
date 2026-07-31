"""
Пути к файлам по спецификации XDG Base Directory.

Конфиг — в ``$XDG_CONFIG_HOME/alimony/config.yaml``, историческая выгрузка и
HTML-отчёт — в ``$XDG_DATA_HOME/alimony/``. Выгрузка лежит в data, а не в cache,
потому что её открывают, кладут в бэкап и хранят годами; cache по определению
можно удалить без потерь.
"""

import os
from pathlib import Path

APP_NAME = "alimony"
CONFIG_FILE_NAME = "config.yaml"
LEDGER_FILE_NAME = "ledger.csv"
REPORT_FILE_NAME = "report.html"


def _xdg_dir(env_var: str, fallback: Path) -> Path:
    """
    Каталог из переменной окружения XDG либо запасной вариант.

    :param env_var: имя переменной, например ``XDG_CONFIG_HOME``
    :param fallback: путь по умолчанию
    :return: каталог приложения внутри найденной базы
    """
    raw = os.environ.get(env_var)
    base = Path(raw) if raw else fallback
    return base / APP_NAME


def config_dir() -> Path:
    """
    Каталог конфигурации.

    :return: ``~/.config/alimony`` либо каталог из ``XDG_CONFIG_HOME``
    """
    return _xdg_dir("XDG_CONFIG_HOME", Path.home() / ".config")


def config_path() -> Path:
    """
    Путь к файлу конфигурации.

    :return: ``~/.config/alimony/config.yaml``
    """
    return config_dir() / CONFIG_FILE_NAME


def legacy_config_path() -> Path:
    """
    Прежнее расположение конфига, до перехода на каталог приложения.

    :return: ``~/.config/alimony.yaml``
    """
    return Path.home() / ".config" / f"{APP_NAME}.yaml"


def data_dir() -> Path:
    """
    Каталог данных.

    :return: ``~/.local/share/alimony`` либо каталог из ``XDG_DATA_HOME``
    """
    return _xdg_dir("XDG_DATA_HOME", Path.home() / ".local" / "share")


def ledger_path() -> Path:
    """
    Путь к помесячной выгрузке.

    :return: ``~/.local/share/alimony/ledger.csv``
    """
    return data_dir() / LEDGER_FILE_NAME


def report_path() -> Path:
    """
    Путь к HTML-отчёту.

    :return: ``~/.local/share/alimony/report.html``
    """
    return data_dir() / REPORT_FILE_NAME
