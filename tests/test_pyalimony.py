from pyalimony import __version__
from pyalimony.utils import get_percent_of_salary


def test_version():
    assert __version__ == '0.1.0'


def test_get_percent_of_salary():
    res = get_percent_of_salary(amount=100, percentile=10)
    assert 10 == res
