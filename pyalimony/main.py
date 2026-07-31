#!/usr/bin/env python3
# Author: Michael Savin <mail@jtprog.ru>
# WWW: https://jtprog.ru
"""
Точка входа: разбор аргументов, загрузка конфига, печать отчёта.

Модель расчёта. Из чистого дохода (после НДФЛ) по каждому исполнительному
производству удерживается total_percent. Часть его — текущий платёж по алиментам,
остальное идёт в счёт задолженности. С совершеннолетием ребёнка текущий платёж
прекращается, и всё удержание по этому ИП уходит на долг.

Правовые основания и ссылки на источники — docs/LEGAL.md.
"""

import argparse
import datetime
import sys
from collections.abc import Sequence

from pyalimony.config import default_config_path, load_config
from pyalimony.errors import PyalimonyError
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
        help=f"путь к конфигу (по умолчанию {default_config_path()})",
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
        config = load_config(args.config)
        calc = calculate(config, as_of=as_of)
    except PyalimonyError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    print(render_json(calc) if args.json else report(calc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
