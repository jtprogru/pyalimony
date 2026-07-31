"""Тесты HTML-отчёта."""

import datetime
from html.parser import HTMLParser

import pytest

from pyalimony.html import month_label, render_html, write_html
from pyalimony.ledger import build_ledger, sum_rows
from pyalimony.utils import format_money
from tests.conftest import HISTORY_CONFIG, TODAY

VOID_TAGS = {"meta", "br", "hr", "img", "input", "link", "source", "col"}


class _TagBalance(HTMLParser):
    """Простейшая проверка парности тегов."""

    def __init__(self):
        super().__init__()
        self.stack: list[str] = []
        self.mismatched: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.mismatched.append(tag)


@pytest.fixture
def rows(config_from_text):
    return build_ledger(config_from_text(HISTORY_CONFIG), as_of=TODAY)


@pytest.fixture
def page(rows):
    return render_html(rows, TODAY)


@pytest.mark.parametrize(
    ("month", "expected"),
    [((2026, 4, 1), "апрель 2026"), ((2026, 1, 1), "январь 2026"), ((2025, 12, 1), "декабрь 2025")],
)
def test_month_label(month, expected):
    assert month_label(datetime.date(*month)) == expected


def test_page_is_well_formed(page):
    checker = _TagBalance()
    checker.feed(page)
    assert checker.mismatched == []
    assert checker.stack == []


def test_page_is_self_contained(page):
    """Ни одного внешнего запроса: страница открывается из файловой системы."""
    for marker in ("http://", "https://", "<script", "src="):
        assert marker not in page


def test_page_head(page):
    assert page.startswith("<!doctype html>")
    assert '<html lang="ru">' in page
    assert '<meta charset="utf-8">' in page
    assert "<title>Выплаты на детей</title>" in page
    assert "prefers-color-scheme: dark" in page


def test_report_date_in_the_header(page):
    assert "Отчёт на 31.07.2026" in page


def test_summary_cards(page, rows):
    totals = sum_rows(rows)
    assert "Всего выплачено" in page
    assert "Текущие алименты" in page
    assert "В счёт задолженности" in page
    assert format_money(totals.total) in page


def test_month_count_card(page, rows):
    assert "Месяцев в выгрузке" in page
    assert f'<div class="value">{len({row.month for row in rows})}</div>' in page


def test_unemployment_note(page):
    assert "посчитан по средней зарплате" in page


def test_no_unemployment_note_without_gaps(config_from_text):
    config = HISTORY_CONFIG.replace("        unemployed: true", "        net_monthly: 140000")
    rows = build_ledger(config_from_text(config), as_of=TODAY)
    assert "посчитан по средней зарплате" not in render_html(rows, TODAY)


def test_yearly_table_lists_children(page):
    assert "<h2>По годам</h2>" in page
    assert "Иванов Иван Иванович" in page
    assert "Петров Пётр Петрович" in page
    assert ">2025<" in page
    assert ">2026<" in page


def test_yearly_table_has_a_grand_total(page):
    assert "<tfoot>" in page
    assert "Всего</td>" in page


def test_monthly_table(page):
    assert "<h2>По месяцам</h2>" in page
    assert "апрель 2026" in page
    assert "по средней (п. 4 ст. 113 СК РФ)" in page or "частично по средней" in page


def test_monthly_table_shows_unemployed_days(page):
    assert "без заработка 22 дн." in page


def test_unknown_debt_renders_as_dash(page):
    """До постановления пристава остаток неизвестен."""
    assert "—" in page


def test_footer_disclaimer(page):
    assert "Расчёт справочный" in page
    assert "ст. 113 СК РФ" in page


def test_empty_ledger_renders(page):
    empty = render_html((), TODAY)
    assert "Выгрузка пуста" in empty
    assert "<h2>По годам</h2>" not in empty


def test_render_defaults_to_today(rows):
    assert f"Отчёт на {datetime.date.today():%d.%m.%Y}" in render_html(rows)


def test_child_names_are_escaped(config_from_text):
    config = HISTORY_CONFIG.replace("surname: 'Иванов'", "surname: '<b>Иванов</b>'")
    rows = build_ledger(config_from_text(config), as_of=TODAY)
    page = render_html(rows, TODAY)
    assert "&lt;b&gt;Иванов&lt;/b&gt;" in page
    assert "<b>Иванов</b>" not in page


def test_write_html_creates_parent_dirs(rows, tmp_path):
    path = write_html(rows, tmp_path / "nested" / "deep" / "report.html", TODAY)
    assert path.exists()
    assert path.read_text(encoding="utf-8").startswith("<!doctype html>")
