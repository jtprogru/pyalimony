"""
Расчёт алиментов и остатка задолженности по исполнительным производствам.
"""

from importlib.metadata import PackageNotFoundError, version

from pyalimony.config import Config, load_config
from pyalimony.errors import ConfigError, PyalimonyError
from pyalimony.main import main
from pyalimony.reports import report
from pyalimony.struct import Calculation, Child, calculate

try:
    __version__ = version("pyalimony")
except PackageNotFoundError:  # pragma: no cover - пакет запущен не из установленного дистрибутива
    __version__ = "0.0.0.dev0"

__all__ = [
    "Calculation",
    "Child",
    "Config",
    "ConfigError",
    "PyalimonyError",
    "calculate",
    "load_config",
    "main",
    "report",
]
