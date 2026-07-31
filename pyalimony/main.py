#!/usr/bin/env python3
# Author: Michael Savin <mail@jtprog.ru>
# WWW: https://jtprog.ru
"""
Точка входа: разбор аргументов, загрузка конфига, печать отчёта.

Модель расчёта. Доход задаётся историей периодов с точностью до дня; начисление
за месяц собирается из отрезков пропорционально календарным дням. Из него по
каждому исполнительному производству удерживается total_percent: часть — текущий
платёж по алиментам, остальное идёт в счёт задолженности. С прекращением
обязательства текущий платёж обнуляется, и всё удержание уходит на долг.

Правовые основания и ссылки на источники — docs/LEGAL.md.
"""

import argparse
import datetime
import sys
from collections.abc import Sequence
from pathlib import Path

from pyalimony import paths
from pyalimony.config import default_config_path, load_config
from pyalimony.errors import PyalimonyError
from pyalimony.html import write_html
from pyalimony.ledger import build_ledger, write_csv
from pyalimony.reports import render_json, report
from pyalimony.struct import calculate
from pyalimony.utils import parse_date


def build_parser() -> argparse.ArgumentParser:
    """
    Собрать парсер аргументов командной строки.

    :return: настроенный ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="pyalimony",
        description="Расчёт алиментов и остатка задолженности по исполнительным производствам",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help=f"путь к конфигу (по умолчанию {paths.config_path()})",
    )
    parser.add_argument(
        "--as-of",
        default=None,
        metavar="ДД.ММ.ГГГГ",
        help="расчётная дата (по умолчанию сегодня)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="вывести результат в JSON вместо текстового отчёта",
    )
    parser.add_argument(
        "--ledger",
        action="store_true",
        help=f"записать помесячную выгрузку в CSV ({paths.ledger_path()})",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help=f"записать HTML-отчёт по выгрузке ({paths.report_path()})",
    )
    parser.add_argument(
        "--ledger-path",
        default=None,
        metavar="ПУТЬ",
        help="куда писать CSV-выгрузку вместо пути по умолчанию",
    )
    parser.add_argument(
        "--html-path",
        default=None,
        metavar="ПУТЬ",
        help="куда писать HTML-отчёт вместо пути по умолчанию",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """
    Запустить расчёт.

    :param argv: аргументы командной строки, по умолчанию sys.argv[1:]
    :return: код возврата процесса
    """
    args = build_parser().parse_args(argv)
    try:
        as_of = parse_date(args.as_of, "--as-of") if args.as_of else datetime.date.today()
        config = load_config(args.config or default_config_path())
        calc = calculate(config, as_of=as_of)
        rows = build_ledger(config, as_of=as_of) if (args.ledger or args.html) else ()
        if args.ledger:
            written = write_csv(rows, Path(args.ledger_path) if args.ledger_path else paths.ledger_path())
            print(f"Выгрузка: {written}")
        if args.html:
            written = write_html(rows, Path(args.html_path) if args.html_path else paths.report_path(), as_of)
            print(f"Отчёт: {written}")
    except PyalimonyError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Ошибка записи: {exc}", file=sys.stderr)
        return 1

    if not (args.ledger or args.html):
        print(render_json(calc) if args.json else report(calc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
