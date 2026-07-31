"""Тесты отрисовки отчёта."""

import datetime
import json

import pytest

from pyalimony.reports import as_dict, render_child, render_json, render_summary, render_warnings, report
from tests.conftest import BASE_CONFIG, CLOSED_CONFIG, DISABLED_CONFIG, EMANCIPATED_CONFIG, MINOR_ONLY_CONFIG


@pytest.fixture
def base(calc):
    return calc()


@pytest.fixture
def rendered(base):
    return report(base)


def test_header_shows_date_and_income(rendered):
    assert rendered.startswith("Расчёт на 31.07.2026")
    assert "Чистый доход в месяц (после НДФЛ):" in rendered
    assert "100 000.00" in rendered


def test_summary_shows_withholdings_and_take_home(base):
    summary = render_summary(base)
    assert "Удержания по алиментным ИП (70.00 %):" in summary
    assert "Остаётся на руки:" in summary
    assert "30 000.00" in summary
    assert "Предел удержания (ст. 99 ФЗ-229):" in summary
    assert "70.00 %" in summary


def test_other_withholdings_hidden_when_zero(base):
    assert "Прочие удержания" not in render_summary(base)


def test_other_withholdings_shown_when_present(calc):
    result = calc(BASE_CONFIG.replace("other_withholding_percent: 0.0", "other_withholding_percent: 10.0"))
    summary = render_summary(result)
    assert "Прочие удержания (10.00 %):" in summary
    assert "10 000.00" in summary


def test_adult_block(base):
    block = render_child(base.children[0])
    assert "Иванов Иван Иванович, 30.11.2006 г.р. — 19 лет, совершеннолетний с 30.11.2024" in block
    assert "прекращён (ст. 120 СК РФ)" in block
    assert "В счёт задолженности:" in block
    assert "40 000.00" in block


def test_minor_block(base):
    block = render_child(base.children[1])
    assert "11 лет, несовершеннолетний до 08.05.2033" in block
    assert "Текущий платёж (ст. 81 СК РФ):" in block
    assert "25 000.00" in block


def test_fixed_sum_block_cites_article_83(calc):
    config = MINOR_ONLY_CONFIG.replace("alimony_percent: 25.0", "alimony_fixed: 25000")
    block = render_child(calc(config).children[0])
    assert "Текущий платёж (ст. 83 СК РФ):" in block


def test_payoff_forecast(base):
    assert "1 месяц (к 01.08.2026)" in render_child(base.children[0])
    assert "16 месяцев (к 01.11.2027)" in render_child(base.children[1])


def test_months_word_agreement(calc):
    config = MINOR_ONLY_CONFIG.replace("debt: 60000", "debt: 90000")
    assert "2 месяца" in render_child(calc(config).children[0])


def test_no_debt_block(calc):
    result = calc(BASE_CONFIG, as_of=datetime.date(2030, 1, 1))
    assert "задолженности нет" in render_child(result.children[0])


def test_not_repaid_block(calc):
    config = MINOR_ONLY_CONFIG.replace("total_percent: 40.0", "total_percent: 0.0")
    config = config.replace("alimony_percent: 25.0", "alimony_percent: 0.0")
    assert "не гасится" in render_child(calc(config).children[0])


def test_total_debt_line(rendered):
    assert "Суммарный остаток задолженности:" in rendered
    assert "120 000.00" in rendered


def test_warnings_block(base):
    block = render_warnings(base)
    assert block.startswith("\nЗамечания:\n")
    assert "  ! " in block


def test_warnings_block_empty_when_clean(calc):
    result = calc(BASE_CONFIG, as_of=datetime.date(2030, 1, 1))
    clean = type(result)(
        as_of=result.as_of,
        income=result.income,
        other_withholding_percent=result.other_withholding_percent,
        children=result.children,
        warnings=(),
    )
    assert render_warnings(clean) == ""


def test_every_child_is_rendered(rendered):
    assert "Иванов Иван Иванович" in rendered
    assert "Петров Пётр Петрович" in rendered


def test_report_has_no_horizontal_overflow(rendered):
    assert all(len(line) <= 119 for line in rendered.splitlines())


def test_as_dict_shape(base):
    data = as_dict(base)
    assert data["as_of"] == "2026-07-31"
    assert data["net_income"] == 100000.0
    assert data["take_home"] == 30000.0
    assert data["withholding_limit"] == 70.0
    assert data["total_debt"] == 120000.0
    assert len(data["children"]) == 2
    assert data["warnings"] == list(base.warnings)


def test_as_dict_child_shape(base):
    child = as_dict(base)["children"][0]
    assert child["full_name"] == "Иванов Иван Иванович"
    assert child["birthday"] == "2006-11-30"
    assert child["majority_date"] == "2024-11-30"
    assert child["is_minor"] is False
    assert child["alimony_amount"] == 0.0
    assert child["debt_payment"] == 40000.0
    assert child["current_debt"] == 40000.0
    assert child["months_left"] == 1
    assert child["payoff_date"] == "2026-08-01"
    assert child["is_closable"] is False


def test_as_dict_handles_missing_payoff(calc):
    config = MINOR_ONLY_CONFIG.replace("total_percent: 40.0", "total_percent: 0.0")
    config = config.replace("alimony_percent: 25.0", "alimony_percent: 0.0")
    child = as_dict(calc(config))["children"][0]
    assert child["months_left"] is None
    assert child["payoff_date"] is None


def test_render_json_is_valid_json(base):
    data = json.loads(render_json(base))
    assert data["as_of"] == "2026-07-31"
    assert data["children"][1]["full_name"] == "Петров Пётр Петрович"


def test_render_json_keeps_cyrillic_readable(base):
    assert "Иванов" in render_json(base)


def test_closed_order_renders_one_line(calc):
    block = render_child(calc(CLOSED_CONFIG).children[0])
    assert block.strip() == "Первый Ребёнок, 01.01.2000 г.р. — производство прекращено"


def test_closed_order_has_no_amounts(calc):
    block = render_child(calc(CLOSED_CONFIG).children[0])
    assert "Текущий платёж" not in block
    assert "Погашение" not in block


def test_disabled_adult_status_and_basis(calc):
    block = render_child(calc(DISABLED_CONFIG).children[0])
    assert "нетрудоспособный — обязательство бессрочно (ст. 85 СК РФ)" in block
    assert "Текущий платёж (ст. 85 СК РФ):" in block
    assert "20 000.00" in block


def test_early_termination_status(calc):
    block = render_child(calc(EMANCIPATED_CONFIG).children[0])
    assert "обязательство прекращено досрочно 01.03.2026" in block
    assert "прекращён (ст. 120 СК РФ)" in block


def test_active_early_termination_status(calc):
    """До наступления даты прекращения статус говорит о сроке, а не о возрасте."""
    block = render_child(calc(EMANCIPATED_CONFIG, as_of=datetime.date(2026, 2, 1)).children[0])
    assert "обязательство действует до 01.03.2026" in block


def test_debt_rows_hidden_without_debt(calc):
    block = render_child(calc(CLOSED_CONFIG).children[1])
    assert "Задолженность на" not in block
    assert "Остаток на расчётную дату:" not in block
    assert "задолженности нет" in block


def test_debt_rows_shown_with_debt(base):
    block = render_child(base.children[0])
    assert "Задолженность на 01.03.2026:" in block
    assert "Остаток на расчётную дату:" in block


@pytest.mark.parametrize(
    ("birthday", "expected"),
    [("01.01.2005", "21 год"), ("01.01.2004", "22 года"), ("01.01.2000", "26 лет")],
)
def test_age_word_agreement(calc, birthday, expected):
    config = DISABLED_CONFIG.replace("birthday: '01.01.2000'", f"birthday: '{birthday}'")
    assert expected in render_child(calc(config).children[0])


def test_as_dict_exposes_obligation_state(calc):
    child = as_dict(calc(EMANCIPATED_CONFIG))["children"][0]
    assert child["obligation_end"] == "2026-03-01"
    assert child["obligation_active"] is False
    assert child["ended_early"] is True
    assert child["closed"] is False
    assert child["disabled"] is False


def test_as_dict_for_disabled_child(calc):
    child = as_dict(calc(DISABLED_CONFIG))["children"][0]
    assert child["obligation_end"] is None
    assert child["obligation_active"] is True
    assert child["disabled"] is True


def test_as_dict_for_closed_order(calc):
    child = as_dict(calc(CLOSED_CONFIG))["children"][0]
    assert child["closed"] is True
    assert child["obligation_active"] is False
    assert child["total_payment"] == 0.0


def test_summary_notes_partially_unemployed_month(calc):
    from tests.conftest import HISTORY_CONFIG

    summary = render_summary(calc(HISTORY_CONFIG, as_of=datetime.date(2026, 4, 15)))
    assert "часть месяца без заработка" in summary
    assert "п. 4 ст. 113 СК РФ" in summary


def test_summary_has_no_note_for_a_plain_month(base):
    assert "ст. 113 СК РФ" not in render_summary(base)
