import tomllib
from pathlib import Path

from pyalimony import __version__
from pyalimony.utils import get_percent_of_salary


def test_version():
    """__version__ должен совпадать с версией в pyproject.toml."""
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == pyproject["project"]["version"]


def test_get_percent_of_salary():
    res = get_percent_of_salary(amount=100, percentile=10)
    assert res == 10
