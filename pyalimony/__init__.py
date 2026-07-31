"""
Рассчет алиментов
"""

from importlib.metadata import PackageNotFoundError, version

from pyalimony.main import main

try:
    __version__ = version("pyalimony")
except PackageNotFoundError:  # pragma: no cover - пакет запущен не из установленного дистрибутива
    __version__ = "0.0.0.dev0"

__all__ = ["main"]
