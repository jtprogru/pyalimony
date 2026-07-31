"""
Ошибки пакета.
"""


class PyalimonyError(Exception):
    """Базовая ошибка pyalimony."""


class ConfigError(PyalimonyError):
    """Конфиг не найден, не разобран или не прошёл валидацию."""
