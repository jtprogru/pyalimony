"""Тесты загрузки и валидации конфига."""

import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from pyalimony.config import default_config_path, load_config
from pyalimony.errors import ConfigError
from tests.conftest import BASE_CONFIG


def test_loads_income_and_children(load):
    config = load(BASE_CONFIG)
    assert config.net_income == Decimal("100000.00")
    assert config.other_withholding_percent == Decimal("0.0")
    assert len(config.children) == 2


def test_child_fields(load):
    child = load(BASE_CONFIG).children[0]
    assert child.surname == "Иванов"
    assert child.name == "Иван"
    assert child.patronymic == "Иванович"
    assert child.full_name == "Иванов Иван Иванович"
    assert child.birthday == datetime.date(2006, 11, 30)


def test_order_fields(load):
    order = load(BASE_CONFIG).children[0].alimony
    assert order.total_percent == Decimal("40.0")
    assert order.alimony_percent == Decimal("25.0")
    assert order.alimony_fixed is None
    assert order.debt == Decimal("200000.00")
    assert order.debt_as_of == datetime.date(2026, 3, 1)
    assert order.is_fixed is False


def test_patronymic_is_optional(load):
    config = load("""
        ---
        net_income: 100000
        children:
          - surname: 'Иванов'
            name: 'Иван'
            birthday: '01.01.2015'
            alimony:
              total_percent: 25.0
              alimony_percent: 25.0
        """)
    child = config.children[0]
    assert child.patronymic == ""
    assert child.full_name == "Иванов Иван"


def test_fixed_sum_order(load):
    """ст. 83 СК РФ — алименты в твёрдой денежной сумме."""
    config = load("""
        ---
        net_income: 100000
        children:
          - surname: 'Иванов'
            name: 'Иван'
            birthday: '01.01.2015'
            alimony:
              total_percent: 30.0
              alimony_fixed: 15000
        """)
    order = config.children[0].alimony
    assert order.is_fixed is True
    assert order.alimony_fixed == Decimal("15000.00")
    assert order.alimony_percent is None


def test_debt_defaults_to_zero_with_today_snapshot(load):
    config = load("""
        ---
        net_income: 100000
        children:
          - surname: 'Иванов'
            name: 'Иван'
            birthday: '01.01.2015'
            alimony:
              total_percent: 25.0
              alimony_percent: 25.0
        """)
    order = config.children[0].alimony
    assert order.debt == Decimal("0.00")
    assert order.debt_as_of == datetime.date.today()


def test_default_config_path_points_to_home():
    path = default_config_path()
    assert path == Path.home() / ".config" / "alimony.yaml"


def test_missing_file_gives_readable_error(tmp_path):
    with pytest.raises(ConfigError, match="Конфиг не найден"):
        load_config(tmp_path / "нет-такого.yaml")


def test_directory_instead_of_file(tmp_path):
    with pytest.raises(ConfigError, match="Не удалось прочитать"):
        load_config(tmp_path)


def test_broken_yaml_gives_readable_error(write_config):
    with pytest.raises(ConfigError, match="Некорректный YAML"):
        load_config(write_config("---\nnet_income: [unclosed\n"))


def test_non_mapping_top_level(write_config):
    with pytest.raises(ConfigError, match="ожидался словарь на верхнем уровне"):
        load_config(write_config("---\n- один\n- два\n"))


def test_empty_file(write_config):
    with pytest.raises(ConfigError, match="ожидался словарь на верхнем уровне"):
        load_config(write_config(""))


@pytest.mark.parametrize("key", ["net_income", "children"])
def test_missing_required_top_level_key(load, key):
    text = BASE_CONFIG.replace(f"{key}:", f"unused_{key}:", 1)
    with pytest.raises(ConfigError, match=key):
        load(text)


@pytest.mark.parametrize("value", ["0", "-1"])
def test_non_positive_income(load, value):
    with pytest.raises(ConfigError, match="доход должен быть положительным"):
        load(BASE_CONFIG.replace("net_income: 100000", f"net_income: {value}"))


def test_income_must_be_a_number(load):
    with pytest.raises(ConfigError, match="net_income"):
        load(BASE_CONFIG.replace("net_income: 100000", "net_income: много"))


@pytest.mark.parametrize("value", ["-1.0", "101.0"])
def test_other_withholding_out_of_range(load, value):
    with pytest.raises(ConfigError, match="other_withholding_percent"):
        load(BASE_CONFIG.replace("other_withholding_percent: 0.0", f"other_withholding_percent: {value}"))


def test_children_must_be_a_non_empty_list(write_config):
    with pytest.raises(ConfigError, match="непустой список"):
        load_config(write_config("---\nnet_income: 100000\nchildren: []\n"))


def test_child_must_be_a_mapping(write_config):
    with pytest.raises(ConfigError, match=r"children\[1\]"):
        load_config(write_config("---\nnet_income: 100000\nchildren:\n  - просто строка\n"))


def test_empty_surname_rejected(load):
    with pytest.raises(ConfigError, match="не могут быть пустыми"):
        load(BASE_CONFIG.replace("surname: 'Иванов'", "surname: '  '"))


def test_birthday_in_the_future_rejected(load):
    future = datetime.date.today().replace(year=datetime.date.today().year + 1)
    with pytest.raises(ConfigError, match="в будущем"):
        load(BASE_CONFIG.replace("birthday: '30.11.2006'", f"birthday: '{future:%d.%m.%Y}'"))


@pytest.mark.parametrize("value", ["-1.0", "101.0"])
def test_total_percent_out_of_range(load, value):
    with pytest.raises(ConfigError, match="total_percent"):
        load(BASE_CONFIG.replace("total_percent: 40.0", f"total_percent: {value}"))


def test_alimony_percent_above_total_rejected(load):
    """Иначе платёж в счёт долга получался бы отрицательным."""
    with pytest.raises(ConfigError, match="больше всего удержания по ИП"):
        load(
            BASE_CONFIG.replace(
                "alimony_percent: 25.0\n      debt: 200000", "alimony_percent: 55.0\n      debt: 200000"
            )
        )


def test_negative_alimony_percent_rejected(load):
    with pytest.raises(ConfigError, match="не может быть отрицательным"):
        load(
            BASE_CONFIG.replace(
                "alimony_percent: 25.0\n      debt: 200000", "alimony_percent: -5.0\n      debt: 200000"
            )
        )


def test_negative_fixed_sum_rejected(write_config):
    with pytest.raises(ConfigError, match="не может быть отрицательной"):
        load_config(
            write_config(
                "---\nnet_income: 100000\nchildren:\n"
                "  - surname: 'И'\n    name: 'И'\n    birthday: '01.01.2015'\n"
                "    alimony:\n      total_percent: 30.0\n      alimony_fixed: -1\n"
            )
        )


def test_both_percent_and_fixed_rejected(write_config):
    with pytest.raises(ConfigError, match="но не оба"):
        load_config(
            write_config(
                "---\nnet_income: 100000\nchildren:\n"
                "  - surname: 'И'\n    name: 'И'\n    birthday: '01.01.2015'\n"
                "    alimony:\n      total_percent: 30.0\n      alimony_percent: 25.0\n      alimony_fixed: 15000\n"
            )
        )


def test_neither_percent_nor_fixed_rejected(write_config):
    with pytest.raises(ConfigError, match="нужен либо alimony_percent"):
        load_config(
            write_config(
                "---\nnet_income: 100000\nchildren:\n"
                "  - surname: 'И'\n    name: 'И'\n    birthday: '01.01.2015'\n"
                "    alimony:\n      total_percent: 30.0\n"
            )
        )


def test_order_must_be_a_mapping(write_config):
    with pytest.raises(ConfigError, match="alimony: ожидался словарь"):
        load_config(
            write_config(
                "---\nnet_income: 100000\nchildren:\n"
                "  - surname: 'И'\n    name: 'И'\n    birthday: '01.01.2015'\n    alimony: 25\n"
            )
        )


def test_negative_debt_rejected(load):
    with pytest.raises(ConfigError, match="задолженность не может быть отрицательной"):
        load(BASE_CONFIG.replace("debt: 200000", "debt: -1"))


def test_debt_without_snapshot_date_rejected(load):
    """Задолженность без даты постановления пристава бессмысленна (ст. 113 СК РФ)."""
    with pytest.raises(ConfigError, match="нужна дата debt_as_of"):
        load(BASE_CONFIG.replace("      debt_as_of: '01.03.2026'\n", "", 1))


def test_debt_snapshot_in_the_future_rejected(load):
    future = datetime.date.today().replace(year=datetime.date.today().year + 1)
    with pytest.raises(ConfigError, match="в будущем"):
        load(BASE_CONFIG.replace("debt_as_of: '01.03.2026'", f"debt_as_of: '{future:%d.%m.%Y}'"))


def test_debt_snapshot_before_birth_rejected(load):
    with pytest.raises(ConfigError, match="раньше рождения ребёнка"):
        load(BASE_CONFIG.replace("debt_as_of: '01.03.2026'", "debt_as_of: '01.03.2000'"))


def test_sum_of_withholdings_above_100_rejected(load):
    with pytest.raises(ConfigError, match="превышает 100 %"):
        load(BASE_CONFIG.replace("other_withholding_percent: 0.0", "other_withholding_percent: 40.0"))


def test_iso_date_format_accepted(load):
    config = load(BASE_CONFIG.replace("birthday: '30.11.2006'", "birthday: '2006-11-30'"))
    assert config.children[0].birthday == datetime.date(2006, 11, 30)


def test_native_yaml_date_accepted(load):
    """Некавыченная дата разбирается YAML в date — это тоже должно работать."""
    config = load(BASE_CONFIG.replace("birthday: '30.11.2006'", "birthday: 2006-11-30"))
    assert config.children[0].birthday == datetime.date(2006, 11, 30)


def test_repository_sample_config_is_valid():
    """Образец config.yaml из репозитория обязан проходить валидацию."""
    config = load_config(Path(__file__).parents[1] / "config.yaml")
    assert config.children


def test_closed_order(load):
    """Прекращённое ИП описывается одним флагом, остальные поля не нужны."""
    config = load("""
        ---
        net_income: 100000
        children:
          - surname: 'Иванов'
            name: 'Иван'
            birthday: '01.01.2000'
            alimony:
              closed: true
        """)
    order = config.children[0].alimony
    assert order.closed is True
    assert order.total_percent == Decimal("0")
    assert order.debt == Decimal("0")
    assert order.alimony_percent is None


def test_closed_order_with_withholding_rejected(load):
    with pytest.raises(ConfigError, match="помечено closed, но удерживает"):
        load("""
            ---
            net_income: 100000
            children:
              - surname: 'Иванов'
                name: 'Иван'
                birthday: '01.01.2000'
                alimony:
                  closed: true
                  total_percent: 25.0
            """)


def test_closed_order_with_debt_rejected(load):
    """Пока долг не погашен, производство не прекращается."""
    with pytest.raises(ConfigError, match="помечено closed при непогашенной задолженности"):
        load("""
            ---
            net_income: 100000
            children:
              - surname: 'Иванов'
                name: 'Иван'
                birthday: '01.01.2000'
                alimony:
                  closed: true
                  debt: 1000
                  debt_as_of: '01.03.2026'
            """)


def test_closed_flag_must_be_boolean(load):
    with pytest.raises(ConfigError, match="ожидается true или false"):
        load(BASE_CONFIG.replace("total_percent: 40.0", "closed: 'да'\n      total_percent: 40.0"))


def test_disabled_flag(load):
    """ст. 85 СК РФ — нетрудоспособный совершеннолетний ребёнок."""
    config = load(BASE_CONFIG.replace("patronymic: 'Иванович'", "patronymic: 'Иванович'\n    disabled: true"))
    assert config.children[0].disabled is True
    assert config.children[1].disabled is False


def test_disabled_flag_must_be_boolean(load):
    with pytest.raises(ConfigError, match="disabled"):
        load(BASE_CONFIG.replace("patronymic: 'Иванович'", "patronymic: 'Иванович'\n    disabled: 1"))


def test_obligation_ended(load):
    """Досрочное прекращение: эмансипация, брак до 18 лет, усыновление."""
    config = load(
        BASE_CONFIG.replace("birthday: '08.05.2015'", "birthday: '08.05.2010'\n    obligation_ended: '01.06.2026'")
    )
    assert config.children[1].obligation_ended == datetime.date(2026, 6, 1)


def test_obligation_ended_before_birth_rejected(load):
    with pytest.raises(ConfigError, match="не позже рождения ребёнка"):
        load(
            BASE_CONFIG.replace("birthday: '30.11.2006'", "birthday: '30.11.2006'\n    obligation_ended: '01.01.2000'")
        )


def test_obligation_ended_in_the_future_rejected(load):
    future = datetime.date.today().replace(year=datetime.date.today().year + 1)
    with pytest.raises(ConfigError, match="в будущем"):
        load(
            BASE_CONFIG.replace(
                "birthday: '30.11.2006'", f"birthday: '30.11.2006'\n    obligation_ended: '{future:%d.%m.%Y}'"
            )
        )


def test_obligation_ended_must_be_a_date(load):
    with pytest.raises(ConfigError, match="obligation_ended"):
        load(BASE_CONFIG.replace("birthday: '30.11.2006'", "birthday: '30.11.2006'\n    obligation_ended: 'когда-то'"))
