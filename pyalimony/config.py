"""
Чтение и валидация конфигурации.

Импорт этого модуля ничего не читает с диска — конфиг загружается явным вызовом
``load_config()``. Все проверки делаются здесь, чтобы дальше по коду данные были
заведомо согласованными.
"""

import datetime
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ruamel.yaml import YAML, YAMLError

from pyalimony.errors import ConfigError
from pyalimony.utils import HUNDRED, ZERO, format_date, parse_date, to_decimal, to_money

_yaml = YAML(typ="safe", pure=True)


def default_config_path() -> Path:
    """
    Путь к конфигу по умолчанию.

    :return: ``~/.config/alimony.yaml``
    """
    return Path.home() / ".config" / "alimony.yaml"


@dataclass(frozen=True, slots=True)
class AlimonyOrder:
    """
    Исполнительное производство по одному ребёнку.

    :param total_percent: весь процент, удерживаемый по этому ИП
    :param alimony_percent: текущий платёж как доля заработка (ст. 81 СК РФ)
    :param alimony_fixed: текущий платёж в твёрдой сумме (ст. 83 СК РФ)
    :param debt: задолженность на дату debt_as_of
    :param debt_as_of: дата, на которую известна задолженность (ст. 113 СК РФ)
    :param closed: производство прекращено — удержаний по нему больше нет
    """

    total_percent: Decimal
    alimony_percent: Decimal | None
    alimony_fixed: Decimal | None
    debt: Decimal
    debt_as_of: datetime.date
    closed: bool = False

    @property
    def is_fixed(self) -> bool:
        """Назначен ли текущий платёж в твёрдой денежной сумме."""
        return self.alimony_fixed is not None


@dataclass(frozen=True, slots=True)
class ChildConfig:
    """
    Ребёнок и относящееся к нему исполнительное производство.

    :param surname: фамилия
    :param name: имя
    :param patronymic: отчество
    :param birthday: дата рождения
    :param alimony: параметры ИП
    :param obligation_ended: фактическая дата прекращения алиментного обязательства,
        если оно прекратилось раньше совершеннолетия (ст. 120 СК РФ): эмансипация,
        брак до 18 лет, усыновление ребёнка другим лицом
    :param disabled: нетрудоспособный ребёнок — обязательство не прекращается
        с совершеннолетием (ст. 85 СК РФ)
    """

    surname: str
    name: str
    patronymic: str
    birthday: datetime.date
    alimony: AlimonyOrder
    obligation_ended: datetime.date | None = None
    disabled: bool = False

    @property
    def full_name(self) -> str:
        """ФИО одной строкой."""
        return " ".join(part for part in (self.surname, self.name, self.patronymic) if part)


@dataclass(frozen=True, slots=True)
class Config:
    """
    Разобранный конфиг.

    :param net_income: чистый доход в месяц после НДФЛ
    :param other_withholding_percent: удержания по неалиментным ИП, процентов
    :param children: дети с их исполнительными производствами
    """

    net_income: Decimal
    other_withholding_percent: Decimal
    children: tuple[ChildConfig, ...]


def load_config(path: Path | str | None = None) -> Config:
    """
    Прочитать и проверить конфиг.

    :param path: путь к YAML-файлу, по умолчанию ``~/.config/alimony.yaml``
    :return: разобранный конфиг
    :raises ConfigError: файла нет, YAML битый или данные не прошли валидацию
    """
    config_path = Path(path) if path is not None else default_config_path()
    try:
        raw_text = config_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(
            f"Конфиг не найден: {config_path}\nСоздайте его из примера: cp config.yaml {config_path}"
        ) from exc
    except OSError as exc:
        raise ConfigError(f"Не удалось прочитать {config_path}: {exc}") from exc

    try:
        data = _yaml.load(raw_text)
    except YAMLError as exc:
        raise ConfigError(f"Некорректный YAML в {config_path}:\n{exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"{config_path}: ожидался словарь на верхнем уровне")

    return parse_config(data)


def parse_config(data: dict) -> Config:
    """
    Собрать Config из словаря и провалидировать его.

    :param data: содержимое YAML
    :return: разобранный конфиг
    :raises ConfigError: данные не прошли валидацию
    """
    net_income = to_money(_require(data, "net_income"), "net_income")
    if net_income <= ZERO:
        raise ConfigError(f"net_income: доход должен быть положительным, получено {net_income}")

    other = to_decimal(data.get("other_withholding_percent", 0), "other_withholding_percent")
    if other < ZERO or other > HUNDRED:
        raise ConfigError(f"other_withholding_percent: ожидается 0..100, получено {other}")

    raw_children = _require(data, "children")
    if not isinstance(raw_children, list) or not raw_children:
        raise ConfigError("children: ожидается непустой список детей")

    children = tuple(_parse_child(item, index) for index, item in enumerate(raw_children, start=1))

    total = sum((child.alimony.total_percent for child in children), start=Decimal("0"))
    if total + other > HUNDRED:
        raise ConfigError(
            f"Суммарное удержание {total + other} % превышает 100 % дохода: "
            f"алименты {total} % + прочие удержания {other} %"
        )

    return Config(net_income=net_income, other_withholding_percent=other, children=children)


def _require(data: dict, key: str) -> object:
    if key not in data:
        raise ConfigError(f"В конфиге отсутствует обязательный ключ {key!r}")
    return data[key]


def _parse_bool(value: object, field: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ConfigError(f"{field}: ожидается true или false, получено {value!r}")


def _parse_child(item: object, index: int) -> ChildConfig:
    where = f"children[{index}]"
    if not isinstance(item, dict):
        raise ConfigError(f"{where}: ожидался словарь, получено {item!r}")

    birthday = parse_date(_require(item, "birthday"), f"{where}.birthday")
    today = datetime.date.today()
    if birthday > today:
        raise ConfigError(f"{where}.birthday: дата рождения {format_date(birthday)} в будущем")

    obligation_ended = None
    if item.get("obligation_ended") is not None:
        obligation_ended = parse_date(item["obligation_ended"], f"{where}.obligation_ended")
        if obligation_ended <= birthday:
            raise ConfigError(
                f"{where}.obligation_ended: дата {format_date(obligation_ended)} не позже рождения ребёнка"
            )
        if obligation_ended > today:
            raise ConfigError(
                f"{where}.obligation_ended: дата {format_date(obligation_ended)} в будущем — "
                f"поле описывает уже наступивший факт прекращения обязательства"
            )

    child = ChildConfig(
        surname=str(_require(item, "surname")).strip(),
        name=str(_require(item, "name")).strip(),
        patronymic=str(item.get("patronymic", "")).strip(),
        birthday=birthday,
        alimony=_parse_order(_require(item, "alimony"), where, birthday),
        obligation_ended=obligation_ended,
        disabled=_parse_bool(item.get("disabled", False), f"{where}.disabled"),
    )
    if not child.surname or not child.name:
        raise ConfigError(f"{where}: surname и name не могут быть пустыми")
    return child


def _parse_order(item: object, where: str, birthday: datetime.date) -> AlimonyOrder:
    where = f"{where}.alimony"
    if not isinstance(item, dict):
        raise ConfigError(f"{where}: ожидался словарь, получено {item!r}")

    today = datetime.date.today()
    closed = _parse_bool(item.get("closed", False), f"{where}.closed")
    if closed:
        return _parse_closed_order(item, where, today)

    total_percent = to_decimal(_require(item, "total_percent"), f"{where}.total_percent")
    if total_percent < ZERO or total_percent > HUNDRED:
        raise ConfigError(f"{where}.total_percent: ожидается 0..100, получено {total_percent}")

    has_percent = item.get("alimony_percent") is not None
    has_fixed = item.get("alimony_fixed") is not None
    if has_percent and has_fixed:
        raise ConfigError(
            f"{where}: укажите либо alimony_percent (ст. 81 СК РФ), либо alimony_fixed (ст. 83 СК РФ), но не оба"
        )
    if not has_percent and not has_fixed:
        raise ConfigError(f"{where}: нужен либо alimony_percent, либо alimony_fixed")

    alimony_percent: Decimal | None = None
    alimony_fixed: Decimal | None = None
    if has_percent:
        alimony_percent = to_decimal(item["alimony_percent"], f"{where}.alimony_percent")
        if alimony_percent < ZERO:
            raise ConfigError(f"{where}.alimony_percent: не может быть отрицательным")
        if alimony_percent > total_percent:
            raise ConfigError(
                f"{where}: текущий платёж {alimony_percent} % больше всего удержания по ИП {total_percent} %"
            )
    else:
        alimony_fixed = to_money(item["alimony_fixed"], f"{where}.alimony_fixed")
        if alimony_fixed < ZERO:
            raise ConfigError(f"{where}.alimony_fixed: не может быть отрицательной")

    debt = to_money(item.get("debt", 0), f"{where}.debt")
    if debt < ZERO:
        raise ConfigError(f"{where}.debt: задолженность не может быть отрицательной")

    if "debt_as_of" in item and item["debt_as_of"] is not None:
        debt_as_of = parse_date(item["debt_as_of"], f"{where}.debt_as_of")
    elif debt > ZERO:
        raise ConfigError(
            f"{where}: при ненулевой задолженности нужна дата debt_as_of — "
            f"дата постановления пристава, на которую посчитан остаток (ст. 113 СК РФ)"
        )
    else:
        debt_as_of = today

    if debt_as_of > today:
        raise ConfigError(f"{where}.debt_as_of: дата {format_date(debt_as_of)} в будущем")
    if debt_as_of < birthday:
        raise ConfigError(
            f"{where}.debt_as_of: дата {format_date(debt_as_of)} раньше рождения ребёнка {format_date(birthday)}"
        )

    return AlimonyOrder(
        total_percent=total_percent,
        alimony_percent=alimony_percent,
        alimony_fixed=alimony_fixed,
        debt=debt,
        debt_as_of=debt_as_of,
        closed=False,
    )


def _parse_closed_order(item: dict, where: str, today: datetime.date) -> AlimonyOrder:
    """
    Разобрать прекращённое производство.

    По нему ничего не удерживается и задолженности не остаётся, поэтому остальные
    поля не требуются — но если их указали, они обязаны быть нулевыми.
    """
    total_percent = to_decimal(item.get("total_percent", 0), f"{where}.total_percent")
    if total_percent > ZERO:
        raise ConfigError(
            f"{where}: производство помечено closed, но удерживает {total_percent} %. "
            f"Уберите closed либо обнулите total_percent"
        )
    debt = to_money(item.get("debt", 0), f"{where}.debt")
    if debt > ZERO:
        raise ConfigError(
            f"{where}: производство помечено closed при непогашенной задолженности {debt} руб. "
            f"Пока долг не закрыт, производство не прекращается"
        )
    return AlimonyOrder(
        total_percent=ZERO,
        alimony_percent=None,
        alimony_fixed=None,
        debt=ZERO,
        debt_as_of=today,
        closed=True,
    )
