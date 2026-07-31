"""
HTML-отчёт по помесячной выгрузке.

Страница самодостаточная: стили встроены, внешних запросов нет, открывается
двойным кликом из файловой системы. Тёмная тема подхватывается системной.
"""

import datetime
import html as html_escape
from decimal import Decimal
from pathlib import Path

from pyalimony.ledger import LedgerRow, Totals, children_names, group_by_year, sum_rows
from pyalimony.utils import format_money

MONTH_NAMES = (
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
)

KIND_LABELS = {
    "salary": "заработок",
    "unemployed": "по средней (п. 4 ст. 113 СК РФ)",
    "mixed": "частично по средней",
    "actual": "фактический доход",
    "none": "нет данных",
}

_STYLE = """
:root { color-scheme: light dark; --fg: #1b1b1b; --muted: #6b6b6b; --line: #e0e0e0;
        --bg: #ffffff; --alt: #f7f7f7; --warn: #b45309; }
@media (prefers-color-scheme: dark) {
  :root { --fg: #e6e6e6; --muted: #9a9a9a; --line: #333; --bg: #161616; --alt: #1e1e1e;
          --warn: #f0a742; }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 2rem 1rem; background: var(--bg); color: var(--fg);
       font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 60rem; margin: 0 auto; }
h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
h2 { font-size: 1.1rem; margin: 2.5rem 0 .75rem; font-weight: 600; }
.sub { color: var(--muted); margin: 0 0 2rem; }
.cards { display: flex; flex-wrap: wrap; gap: .75rem; }
.card { flex: 1 1 12rem; border: 1px solid var(--line); border-radius: .5rem; padding: .75rem 1rem; }
.card .label { color: var(--muted); font-size: .8rem; }
.card .value { font-size: 1.25rem; font-variant-numeric: tabular-nums; margin-top: .25rem; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
th, td { padding: .4rem .6rem; text-align: right; border-bottom: 1px solid var(--line); white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
thead th { font-weight: 600; color: var(--muted); font-size: .8rem; }
tbody tr:nth-child(even) { background: var(--alt); }
tfoot td { font-weight: 600; border-top: 2px solid var(--line); border-bottom: none; }
.note { color: var(--warn); font-size: .8rem; }
footer { color: var(--muted); font-size: .8rem; margin-top: 3rem; }
"""


def _esc(value: object) -> str:
    return html_escape.escape(str(value))


def _money(value: Decimal | None) -> str:
    return "—" if value is None else format_money(value)


def month_label(month: datetime.date) -> str:
    """
    Название месяца с годом.

    :param month: первое число месяца
    :return: строка вида ``апрель 2026``
    """
    return f"{MONTH_NAMES[month.month - 1]} {month.year}"


def _card(label: str, value: str) -> str:
    return f'<div class="card"><div class="label">{_esc(label)}</div><div class="value">{_esc(value)}</div></div>'


def _summary(rows: tuple[LedgerRow, ...], as_of: datetime.date) -> str:
    totals = sum_rows(rows)
    months = len({row.month for row in rows})
    unemployed = sum(1 for row in rows if row.unemployed_days > 0)
    cards = [
        _card("Всего выплачено", _money(totals.total)),
        _card("Текущие алименты", _money(totals.alimony)),
        _card("В счёт задолженности", _money(totals.debt_payment)),
        _card("Месяцев в выгрузке", str(months)),
    ]
    out = f'<h1>Выплаты на детей</h1>\n<p class="sub">Отчёт на {as_of:%d.%m.%Y}</p>\n'
    out += '<div class="cards">' + "".join(cards) + "</div>\n"
    if unemployed:
        out += (
            f'<p class="note">В {unemployed} строках доход за месяц частично или полностью '
            f"посчитан по средней зарплате: в эти дни заработка не было.</p>\n"
        )
    return out


def _totals_row(label: str, totals: Totals, cells: int, tag: str = "td") -> str:
    padding = f"<{tag}></{tag}>" * cells
    return (
        f"<tr><{tag}>{_esc(label)}</{tag}>{padding}"
        f"<{tag}>{_money(totals.alimony)}</{tag}>"
        f"<{tag}>{_money(totals.debt_payment)}</{tag}>"
        f"<{tag}>{_money(totals.total)}</{tag}></tr>"
    )


def _by_year(rows: tuple[LedgerRow, ...]) -> str:
    names = children_names(rows)
    out = '<h2>По годам</h2>\n<div class="scroll"><table>\n<thead><tr><th>Год</th>'
    for name in names:
        out += f"<th>{_esc(name)}</th>"
    out += "<th>Текущие</th><th>Долг</th><th>Итого</th></tr></thead>\n<tbody>\n"

    grand = Totals()
    for year, year_rows in group_by_year(rows).items():
        totals = sum_rows(year_rows)
        out += f"<tr><td>{year}</td>"
        for name in names:
            child_total = sum_rows(tuple(row for row in year_rows if row.child == name)).total
            out += f"<td>{_money(child_total)}</td>"
        out += f"<td>{_money(totals.alimony)}</td><td>{_money(totals.debt_payment)}</td>"
        out += f"<td>{_money(totals.total)}</td></tr>\n"
        grand = Totals(
            alimony=grand.alimony + totals.alimony,
            debt_payment=grand.debt_payment + totals.debt_payment,
            total=grand.total + totals.total,
        )
    out += "</tbody>\n<tfoot>\n" + _totals_row("Всего", grand, len(names)) + "\n</tfoot>\n</table></div>\n"
    return out


def _by_month(rows: tuple[LedgerRow, ...]) -> str:
    out = '<h2>По месяцам</h2>\n<div class="scroll"><table>\n'
    out += (
        "<thead><tr><th>Месяц</th><th>Ребёнок</th><th>Доход за месяц</th><th>Источник</th>"
        "<th>Текущие</th><th>Долг</th><th>Итого</th><th>Остаток долга</th></tr></thead>\n<tbody>\n"
    )
    for row in rows:
        kind = KIND_LABELS.get(row.income_kind, row.income_kind)
        if row.unemployed_days:
            kind += f", без заработка {row.unemployed_days} дн."
        out += (
            f"<tr><td>{_esc(month_label(row.month))}</td><td>{_esc(row.child)}</td>"
            f"<td>{_money(row.income)}</td><td>{_esc(kind)}</td>"
            f"<td>{_money(row.alimony)}</td><td>{_money(row.debt_payment)}</td>"
            f"<td>{_money(row.total)}</td><td>{_money(row.debt_left)}</td></tr>\n"
        )
    out += "</tbody>\n</table></div>\n"
    return out


def render_html(rows: tuple[LedgerRow, ...], as_of: datetime.date | None = None) -> str:
    """
    Собрать HTML-страницу по выгрузке.

    :param rows: строки помесячной выгрузки
    :param as_of: дата отчёта, по умолчанию сегодня
    :return: готовая HTML-страница
    """
    day = as_of or datetime.date.today()
    body = _summary(rows, day)
    if rows:
        body += _by_year(rows)
        body += _by_month(rows)
    else:
        body += "<p>Выгрузка пуста: нет ни одного действующего исполнительного производства.</p>\n"
    body += (
        "<footer>Расчёт справочный. Юридически значимая величина задолженности — та, "
        "что указана в постановлении судебного пристава-исполнителя (ст. 113 СК РФ).</footer>\n"
    )
    return (
        "<!doctype html>\n"
        '<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Выплаты на детей</title>\n"
        f"<style>{_STYLE}</style>\n</head>\n<body>\n<main>\n{body}</main>\n</body>\n</html>\n"
    )


def write_html(rows: tuple[LedgerRow, ...], path: Path, as_of: datetime.date | None = None) -> Path:
    """
    Записать HTML-отчёт, создав каталог при необходимости.

    :param rows: строки выгрузки
    :param path: путь к файлу
    :param as_of: дата отчёта
    :return: путь к записанному файлу
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(rows, as_of), encoding="utf-8")
    return path
