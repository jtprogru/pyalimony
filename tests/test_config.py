"""Тесты загрузки и валидации конфига."""

import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from pyalimony.config import default_config_path, load_config
from pyalimony.errors import ConfigError
from tests.conftest import BASE_CONFIG, HISTORY_CONFIG


def test_loads_income_and_children(load):
    config = load(BASE_CONFIG)
    assert config.income.income_for_month(2026, 7).amount == Decimal("100000.00")
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


def test_income_periods(load):
    config = load(HISTORY_CONFIG)
    assert len(config.income.periods) == 3
    assert config.income.start == datetime.date(2025, 10, 1)
    assert config.income.average_wage == Decimal("87000.00")
    assert config.income.periods[1].unemployed is True
    assert config.income.periods[2].end is None


def test_scalar_income_is_open_ended(load):
    """Постоянный доход покрывает и прошлое: у периода нет даты начала."""
    config = load(BASE_CONFIG)
    assert config.income.start is None
    assert config.income.income_for_month(2010, 1).amount == Decimal("100000.00")


def test_periods_are_sorted(load):
    """Порядок в YAML не важен, отрезки сортируются по дате."""
    reordered = HISTORY_CONFIG.replace(
        "      - from: '01.10.2025'\n        to: '05.04.2026'\n        net_monthly: 140000\n", ""
    ).replace(
        "    average_wage: 87000",
        "      - from: '01.10.2025'\n        to: '05.04.2026'\n        net_monthly: 140000\n\n    average_wage: 87000",
    )
    config = load(reordered)
    assert [period.start for period in config.income.periods] == [
        datetime.date(2025, 10, 1),
        datetime.date(2026, 4, 6),
        datetime.date(2026, 4, 28),
    ]


def test_both_income_forms_rejected(load):
    with pytest.raises(ConfigError, match="но не оба"):
        load(HISTORY_CONFIG.replace("    average_wage: 87000", "    net_income: 100000\n    average_wage: 87000"))


def test_no_income_at_all_rejected(load):
    with pytest.raises(ConfigError, match="'net_income' или 'income'"):
        load(BASE_CONFIG.replace("net_income: 100000", "unused: 1"))


def test_gap_in_income_history_rejected(load):
    """Молчаливая дыра — самый лёгкий способ получить сюрприз, поэтому это ошибка."""
    with pytest.raises(ConfigError, match=r"дыра с 06\.04\.2026 по 27\.04\.2026"):
        load(
            HISTORY_CONFIG.replace(
                "      - from: '06.04.2026'\n        to: '27.04.2026'\n        unemployed: true\n", ""
            )
        )


def test_overlapping_income_periods_rejected(load):
    with pytest.raises(ConfigError, match="пересекается со следующим"):
        load(HISTORY_CONFIG.replace("to: '05.04.2026'", "to: '20.04.2026'"))


def test_open_period_must_be_last(load):
    with pytest.raises(ConfigError, match="только последний период"):
        load(HISTORY_CONFIG.replace("        to: '05.04.2026'\n", ""))


def test_income_period_to_before_from_rejected(load):
    with pytest.raises(ConfigError, match="'to' раньше даты 'from'"):
        load(HISTORY_CONFIG.replace("to: '05.04.2026'", "to: '05.04.2024'"))


def test_income_period_in_the_future_rejected(load):
    future = datetime.date.today().replace(year=datetime.date.today().year + 1)
    with pytest.raises(ConfigError, match="начинается в будущем"):
        load(HISTORY_CONFIG.replace("from: '28.04.2026'", f"from: '{future:%d.%m.%Y}'"))


def test_unemployed_period_needs_average_wage(load):
    with pytest.raises(ConfigError, match="нужен average_wage"):
        load(HISTORY_CONFIG.replace("    average_wage: 87000\n", ""))


def test_period_with_both_income_and_unemployed_rejected(load):
    with pytest.raises(ConfigError, match="одновременно с доходом и без него"):
        load(HISTORY_CONFIG.replace("        unemployed: true", "        unemployed: true\n        net_monthly: 1"))


def test_period_without_income_or_flag_rejected(load):
    with pytest.raises(ConfigError, match="нужен либо net_monthly"):
        load(HISTORY_CONFIG.replace("        unemployed: true", "        unemployed: false"))


def test_negative_period_income_rejected(load):
    with pytest.raises(ConfigError, match="доход не может быть отрицательным"):
        load(HISTORY_CONFIG.replace("net_monthly: 140000", "net_monthly: -1"))


def test_income_must_be_a_list(load):
    with pytest.raises(ConfigError, match="непустой список периодов"):
        load("""
            ---
            income: 100000
            children:
              - surname: 'И'
                name: 'И'
                birthday: '01.01.2015'
                alimony:
                  total_percent: 25.0
                  alimony_percent: 25.0
            """)


def test_income_period_must_be_a_mapping(load):
    with pytest.raises(ConfigError, match=r"income\[1\]: ожидался словарь"):
        load("""
            ---
            income:
              - просто строка
            children:
              - surname: 'И'
                name: 'И'
                birthday: '01.01.2015'
                alimony:
                  total_percent: 25.0
                  alimony_percent: 25.0
            """)


def test_non_positive_average_wage_rejected(load):
    with pytest.raises(ConfigError, match="average_wage"):
        load(HISTORY_CONFIG.replace("average_wage: 87000", "average_wage: 0"))


def test_income_actual_overrides_a_month(load):
    config = load(
        HISTORY_CONFIG.replace(
            "    average_wage: 87000", "    average_wage: 87000\n    income_actual:\n      '04.2026': 152300"
        )
    )
    assert config.income.income_for_month(2026, 4).amount == Decimal("152300.00")


def test_income_actual_accepts_iso_month(load):
    config = load(
        HISTORY_CONFIG.replace(
            "    average_wage: 87000", "    average_wage: 87000\n    income_actual:\n      '2026-04': 152300"
        )
    )
    assert config.income.income_for_month(2026, 4).amount == Decimal("152300.00")


def test_income_actual_must_be_a_mapping(load):
    with pytest.raises(ConfigError, match="income_actual: ожидается словарь"):
        load(HISTORY_CONFIG.replace("    average_wage: 87000", "    average_wage: 87000\n    income_actual: 100"))


def test_income_actual_bad_month_rejected(load):
    with pytest.raises(ConfigError, match="не удалось разобрать месяц"):
        load(
            HISTORY_CONFIG.replace(
                "    average_wage: 87000", "    average_wage: 87000\n    income_actual:\n      'апрель': 1"
            )
        )


def test_income_actual_negative_rejected(load):
    with pytest.raises(ConfigError, match="доход не может быть отрицательным"):
        load(
            HISTORY_CONFIG.replace(
                "    average_wage: 87000", "    average_wage: 87000\n    income_actual:\n      '04.2026': -1"
            )
        )


def test_started_at(load):
    assert load(HISTORY_CONFIG).children[0].alimony.started_at == datetime.date(2025, 10, 1)
    assert load(BASE_CONFIG).children[0].alimony.started_at is None


def test_started_at_before_birth_rejected(load):
    with pytest.raises(ConfigError, match=r"started_at.*раньше рождения"):
        load(HISTORY_CONFIG.replace("started_at: '01.10.2025'", "started_at: '01.10.1990'"))


def test_started_at_in_the_future_rejected(load):
    future = datetime.date.today().replace(year=datetime.date.today().year + 1)
    with pytest.raises(ConfigError, match=r"started_at.*в будущем"):
        load(HISTORY_CONFIG.replace("started_at: '01.10.2025'", f"started_at: '{future:%d.%m.%Y}'"))


def test_default_config_path_prefers_the_app_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".config" / "alimony").mkdir(parents=True)
    (tmp_path / ".config" / "alimony" / "config.yaml").write_text("", encoding="utf-8")
    (tmp_path / ".config" / "alimony.yaml").write_text("", encoding="utf-8")
    assert default_config_path() == tmp_path / ".config" / "alimony" / "config.yaml"


def test_default_config_path_falls_back_to_the_old_location(monkeypatch, tmp_path):
    """Конфиг с прежнего пути продолжает работать, пока его не перенесли."""
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".config").mkdir(parents=True)
    (tmp_path / ".config" / "alimony.yaml").write_text("", encoding="utf-8")
    assert default_config_path() == tmp_path / ".config" / "alimony.yaml"


def test_default_config_path_without_any_file(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert default_config_path() == tmp_path / ".config" / "alimony" / "config.yaml"
