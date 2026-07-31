"""Тесты уровня пакета."""

import tomllib
from pathlib import Path

from pyalimony import __version__


def test_version():
    """__version__ должен совпадать с версией в pyproject.toml."""
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == pyproject["project"]["version"]
