"""Тесты бизнес-логики расчёта."""

import datetime
from decimal import Decimal

import pytest

from pyalimony.struct import calculate
from tests.conftest import BASE_CONFIG, CLOSED_CONFIG, DISABLED_CONFIG, EMANCIPATED_CONFIG, MINOR_ONLY_CONFIG, TODAY


@pytest.fixture
def base(calc):
    return calc()


@pytest.fixture
def adult(base):
    """Иванов, 30.11.2006 — совершеннолетний с 30.11.2024."""
    return base.children[0]


@pytest.fixture
def minor(base):
    """Петров, 08.05.2015 — несовершеннолетний."""
    return base.children[1]


def test_identity(adult):
    assert adult.full_name == "Иванов Иван Иванович"
    assert adult.birthday == datetime.date(2006, 11, 30)
    assert "Иванов" in repr(adult)


def test_majority_and_age(adult, minor):
    assert adult.majority_date == datetime.date(2024, 11, 30)
    assert adult.age == 19
    assert adult.is_minor is False
    assert minor.majority_date == datetime.date(2033, 5, 8)
    assert minor.age == 11
    assert minor.is_minor is True


def test_total_payment(adult, minor):
    assert adult.total_payment == Decimal("40000.00")
    assert minor.total_payment == Decimal("30000.00")


def test_current_alimony_stops_at_majority(adult):
    """Абз. 2 п. 2 ст. 120 СК РФ: после 18 лет текущий платёж прекращается."""
    assert adult.alimony_amount == Decimal("0.00")
    assert adult.debt_payment == Decimal("40000.00")


def test_current_alimony_for_minor(minor):
    assert minor.alimony_amount == Decimal("25000.00")
    assert minor.debt_payment == Decimal("5000.00")


def test_payments_add_up(adult, minor):
    for child in (adult, minor):
        assert child.alimony_amount + child.debt_payment == child.total_payment


def test_months_paid_counts_full_months(adult):
    """01.03.2026 → 31.07.2026 — четыре полных месяца."""
    assert adult.months_paid == 4


def test_current_debt_is_simulated(adult, minor):
    assert adult.current_debt == Decimal("40000.00")  # 200000 - 4 * 40000
    assert minor.current_debt == Decimal("80000.00")  # 100000 - 4 * 5000


def test_months_left_and_payoff_date(adult, minor):
    assert adult.months_left == 1
    assert adult.payoff_date == datetime.date(2026, 8, 1)
    assert minor.months_left == 16
    assert minor.payoff_date == datetime.date(2027, 11, 1)


def test_debt_survives_new_year(calc):
    """Регрессия: старая формула по номерам месяцев в январе увеличивала долг."""
    january = calc(BASE_CONFIG, as_of=datetime.date(2027, 1, 15))
    minor = january.children[1]
    assert minor.months_paid == 10
    assert minor.current_debt == Decimal("50000.00")  # 100000 - 10 * 5000
    assert january.children[0].current_debt == Decimal("0.00")


def test_debt_never_goes_negative(calc):
    """Регрессия: остаток ограничен нулём, месяцы до погашения не отрицательные."""
    far_future = calc(BASE_CONFIG, as_of=datetime.date(2030, 1, 1))
    for child in far_future.children:
        assert child.current_debt == Decimal("0.00")
        assert child.months_left == 0
        assert child.payoff_date is not None


def test_debt_at_snapshot_date_is_untouched(calc):
    """В день постановления пристава ни одного платежа ещё не прошло."""
    same_day = calc(BASE_CONFIG, as_of=datetime.date(2026, 3, 1))
    assert same_day.children[0].months_paid == 0
    assert same_day.children[0].current_debt == Decimal("200000.00")


def test_debt_payment_switches_at_majority(calc):
    """
    Ключевой сценарий: пока ребёнок несовершеннолетний, в долг уходит разница,
    после 18 лет — всё удержание по ИП.
    """
    config = """
        ---
        net_income: 100000
        children:
          - surname: 'Иванов'
            name: 'Иван'
            birthday: '01.06.2008'
            alimony:
              total_percent: 40.0
              alimony_percent: 25.0
              debt: 100000
              debt_as_of: '01.04.2026'
        """
    # Совершеннолетие 01.06.2026. Платежи: 01.05 и 01.06 — по 15000 (несовершеннолетний),
    # дальше по 40000. На 01.08.2026 прошло 4 платежа.
    child = calc(config, as_of=datetime.date(2026, 8, 1)).children[0]
    assert child.months_paid == 4
    # 100000 - 15000 (май) - 40000 (июнь) - 40000 (июль) - 40000 (август) → ноль
    assert child.current_debt == Decimal("0.00")

    mid = calc(config, as_of=datetime.date(2026, 6, 1)).children[0]
    assert mid.months_paid == 2
    assert mid.current_debt == Decimal("45000.00")  # 100000 - 15000 - 40000
    assert mid.alimony_amount == Decimal("0.00")


def test_zero_debt_payment_does_not_crash(calc):
    """
    Регрессия: раньше здесь было деление на ноль.

    Весь удерживаемый процент уходит на текущий платёж, долг стоит на месте —
    и сдвинется только после совершеннолетия, когда текущий платёж прекратится.
    """
    config = """
        ---
        net_income: 100000
        children:
          - surname: 'Сидоров'
            name: 'Сидор'
            birthday: '01.01.2015'
            alimony:
              total_percent: 25.0
              alimony_percent: 25.0
              debt: 50000
              debt_as_of: '01.03.2026'
        """
    child = calc(config).children[0]
    assert child.debt_payment == Decimal("0.00")
    assert child.current_debt == Decimal("50000.00")
    # Совершеннолетие 01.01.2033, после него в долг уходит все 25 % = 25000 в месяц.
    assert child.months_left == 79
    assert child.payoff_date == datetime.date(2033, 2, 1)


def test_debt_never_repaid_when_nothing_is_withheld(calc):
    """Ноль удержания по ИП — прогноз погашения невозможен."""
    config = """
        ---
        net_income: 100000
        children:
          - surname: 'Сидоров'
            name: 'Сидор'
            birthday: '01.01.2015'
            alimony:
              total_percent: 0.0
              alimony_percent: 0.0
              debt: 50000
              debt_as_of: '01.03.2026'
        """
    child = calc(config).children[0]
    assert child.debt_payment == Decimal("0.00")
    assert child.months_left is None
    assert child.payoff_date is None


def test_no_debt_at_all(calc):
    config = """
        ---
        net_income: 100000
        children:
          - surname: 'Сидоров'
            name: 'Сидор'
            birthday: '01.01.2015'
            alimony:
              total_percent: 25.0
              alimony_percent: 25.0
        """
    child = calc(config).children[0]
    assert child.current_debt == Decimal("0.00")
    assert child.months_left == 0
    assert child.is_closable is False  # ребёнок ещё несовершеннолетний


def test_is_closable_for_adult_without_debt(calc):
    child = calc(BASE_CONFIG, as_of=datetime.date(2030, 1, 1)).children[0]
    assert child.is_minor is False
    assert child.current_debt == Decimal("0.00")
    assert child.is_closable is True


def test_fixed_sum_alimony(calc):
    """ст. 83 СК РФ: твёрдая сумма вместо доли."""
    config = """
        ---
        net_income: 100000
        children:
          - surname: 'Иванов'
            name: 'Иван'
            birthday: '01.01.2015'
            alimony:
              total_percent: 30.0
              alimony_fixed: 18000
              debt: 24000
              debt_as_of: '01.03.2026'
        """
    child = calc(config).children[0]
    assert child.alimony_amount == Decimal("18000.00")
    assert child.debt_payment == Decimal("12000.00")
    assert child.current_debt == Decimal("0.00")


def test_fixed_sum_capped_by_total_withholding(calc):
    """Твёрдая сумма не может превышать то, что вообще удерживается по ИП."""
    config = """
        ---
        net_income: 100000
        children:
          - surname: 'Иванов'
            name: 'Иван'
            birthday: '01.01.2015'
            alimony:
              total_percent: 10.0
              alimony_fixed: 50000
        """
    child = calc(config).children[0]
    assert child.total_payment == Decimal("10000.00")
    assert child.alimony_amount == Decimal("10000.00")
    assert child.debt_payment == Decimal("0.00")


def test_calculation_totals(base):
    assert base.as_of == TODAY
    assert base.alimony_percent == Decimal("70.0")
    assert base.alimony_withheld == Decimal("70000.00")
    assert base.other_withheld == Decimal("0.00")
    assert base.total_withheld == Decimal("70000.00")
    assert base.take_home == Decimal("30000.00")
    assert base.total_debt == Decimal("120000.00")


def test_take_home_accounts_for_other_withholdings(calc):
    result = calc(BASE_CONFIG.replace("other_withholding_percent: 0.0", "other_withholding_percent: 10.0"))
    assert result.other_withheld == Decimal("10000.00")
    assert result.total_withheld_percent == Decimal("80.0")
    assert result.total_withheld == Decimal("80000.00")
    assert result.take_home == Decimal("20000.00")


def test_withholding_limit_depends_on_minors(calc):
    """ч. 2-3 ст. 99 ФЗ-229."""
    assert calc(BASE_CONFIG).withholding_limit == Decimal("70")
    grown_up = calc(BASE_CONFIG, as_of=datetime.date(2035, 1, 1))
    assert grown_up.has_minor_children is False
    assert grown_up.withholding_limit == Decimal("50")


def test_calculate_defaults_to_today(config_from_text):
    result = calculate(config_from_text(MINOR_ONLY_CONFIG))
    assert result.as_of == datetime.date.today()


def test_base_config_warns_only_about_penalty(base):
    """Базовый конфиг законодательству не противоречит — остаётся напоминание о ст. 115."""
    assert len(base.warnings) == 1
    assert "неустойка" in base.warnings[0]
    assert "ст. 115" in base.warnings[0]


def test_no_penalty_note_without_debt(calc):
    result = calc(BASE_CONFIG, as_of=datetime.date(2030, 1, 1))
    assert not any("неустойка" in note for note in result.warnings)


def test_warns_when_limit_exceeded(calc):
    """Свыше 70 % при несовершеннолетних детях — ч. 3 ст. 99 ФЗ-229."""
    result = calc(BASE_CONFIG.replace("other_withholding_percent: 0.0", "other_withholding_percent: 25.0"))
    assert any("превышает предел" in note and "ч. 3 ст. 99" in note for note in result.warnings)


def test_warns_when_all_grown_up_and_over_50(calc):
    result = calc(BASE_CONFIG, as_of=datetime.date(2035, 1, 1))
    assert any("Действующих алиментов на несовершеннолетних детей нет" in note for note in result.warnings)
    assert any("превышает предел" in note and "ч. 2 ст. 99" in note for note in result.warnings)


def test_warns_when_share_below_statute(calc):
    """Один несовершеннолетний при 16.6 % вместо 1/4 — п. 1 ст. 81 СК РФ."""
    result = calc(MINOR_ONLY_CONFIG.replace("alimony_percent: 25.0", "alimony_percent: 16.6"))
    note = next(n for n in result.warnings if "ст. 81" in n)
    assert "ниже доли" in note
    assert "25.00 %" in note
    assert "на 1 ребёнка" in note


def test_warns_when_share_above_statute(calc):
    result = calc(MINOR_ONLY_CONFIG.replace("alimony_percent: 25.0", "alimony_percent: 33.0"))
    assert any("выше доли" in note for note in result.warnings)


def test_no_share_warning_for_two_minors_at_one_third(calc):
    config = BASE_CONFIG.replace("birthday: '30.11.2006'", "birthday: '30.11.2016'")
    config = config.replace("alimony_percent: 25.0\n      debt: 200000", "alimony_percent: 16.67\n      debt: 200000")
    config = config.replace("alimony_percent: 25.0\n      debt: 100000", "alimony_percent: 16.66\n      debt: 100000")
    result = calc(config)
    assert not any("ст. 81" in note for note in result.warnings)


def test_no_share_warning_for_fixed_sum(calc):
    """В твёрдой сумме доли по ст. 81 не сравниваются."""
    config = MINOR_ONLY_CONFIG.replace("alimony_percent: 25.0", "alimony_fixed: 5000")
    assert not any("ст. 81" in note for note in calc(config).warnings)


def test_no_share_warning_without_minors(calc):
    result = calc(BASE_CONFIG, as_of=datetime.date(2035, 1, 1))
    assert not any("ст. 81" in note for note in result.warnings)


def test_warns_about_closable_order(calc):
    result = calc(BASE_CONFIG, as_of=datetime.date(2030, 1, 1))
    assert any("подлежит прекращению" in note and "ст. 43 ФЗ-229" in note for note in result.warnings)


def test_warns_when_debt_is_not_repaid(calc):
    """Весь удерживаемый процент уходит на текущий платёж — долг стоит."""
    config = MINOR_ONLY_CONFIG.replace("total_percent: 40.0", "total_percent: 25.0")
    assert any("не гасится" in note for note in calc(config).warnings)


def test_warns_about_stale_debt_snapshot(calc):
    """Снимок задолженности старше полугода нужно сверять (ст. 113 СК РФ)."""
    result = calc(BASE_CONFIG, as_of=datetime.date(2026, 10, 1))
    assert any("ст. 113 СК РФ" in note for note in result.warnings)


def test_no_stale_warning_within_six_months(base):
    assert not any("ст. 113 СК РФ" in note for note in base.warnings)


def test_warns_when_majority_happened_after_snapshot(calc):
    """Совершеннолетие наступило внутри расчётного периода — это стоит подсветить."""
    config = """
        ---
        net_income: 100000
        children:
          - surname: 'Иванов'
            name: 'Иван'
            birthday: '01.06.2008'
            alimony:
              total_percent: 40.0
              alimony_percent: 25.0
              debt: 500000
              debt_as_of: '01.04.2026'
        """
    result = calc(config, as_of=datetime.date(2026, 7, 1))
    assert any("текущий платёж прекращён 01.06.2026" in note for note in result.warnings)


def test_no_majority_note_when_snapshot_is_later(base):
    """Иванов повзрослел до постановления пристава — сообщать не о чем."""
    assert not any("текущий платёж прекращён" in note for note in base.warnings)


def test_closed_order_is_inert(calc):
    """Прекращённое ИП ничего не удерживает и не порождает замечаний."""
    child = calc(CLOSED_CONFIG).children[0]
    assert child.is_closed is True
    assert child.obligation_active is False
    assert child.total_payment == Decimal("0.00")
    assert child.alimony_amount == Decimal("0.00")
    assert child.debt_payment == Decimal("0.00")
    assert child.current_debt == Decimal("0.00")
    assert child.is_closable is False  # прекращать уже нечего


def test_closed_order_excluded_from_totals(calc):
    result = calc(CLOSED_CONFIG)
    assert result.alimony_percent == Decimal("25.0")
    assert result.alimony_withheld == Decimal("25000.00")
    assert result.take_home == Decimal("75000.00")


def test_closed_order_produces_no_warnings(calc):
    result = calc(CLOSED_CONFIG)
    assert not any("Первый" in note for note in result.warnings)


def test_closed_order_does_not_raise_limit(calc):
    """Прекращённое ИП не даёт основания для 70 % по ч. 3 ст. 99 ФЗ-229."""
    config = CLOSED_CONFIG.replace("birthday: '01.01.2015'", "birthday: '01.01.2000'")
    result = calc(config)
    assert result.has_minor_children is False
    assert result.withholding_limit == Decimal("50")


def test_disabled_adult_keeps_paying(calc):
    """ст. 85 СК РФ: обязательство перед нетрудоспособным ребёнком бессрочно."""
    child = calc(DISABLED_CONFIG).children[0]
    assert child.age == 26
    assert child.is_minor is False
    assert child.obligation_end is None
    assert child.obligation_active is True
    assert child.alimony_amount == Decimal("20000.00")
    assert child.debt_payment == Decimal("0.00")


def test_disabled_adult_still_pays_in_far_future(calc):
    child = calc(DISABLED_CONFIG, as_of=datetime.date(2060, 1, 1)).children[0]
    assert child.obligation_active is True
    assert child.alimony_amount == Decimal("20000.00")


def test_disabled_adult_does_not_raise_withholding_limit(calc):
    """Повышенный предел ч. 3 ст. 99 ФЗ-229 привязан к несовершеннолетним детям."""
    result = calc(DISABLED_CONFIG)
    assert result.has_minor_children is False
    assert result.withholding_limit == Decimal("50")


def test_disabled_minor_behaves_as_usual_until_18(calc):
    config = DISABLED_CONFIG.replace("birthday: '01.01.2000'", "birthday: '01.01.2015'")
    result = calc(config)
    child = result.children[0]
    assert child.is_minor is True
    assert child.obligation_active is True
    assert result.withholding_limit == Decimal("70")


def test_warns_when_disabled_adult_paid_by_share(calc):
    """п. 2 ст. 85 СК РФ: взыскание в твёрдой денежной сумме, а не долей."""
    config = DISABLED_CONFIG.replace("alimony_fixed: 20000", "alimony_percent: 20.0")
    assert any("п. 2 ст. 85 СК РФ" in note for note in calc(config).warnings)


def test_no_share_warning_for_disabled_minor(calc):
    """Пока ребёнок несовершеннолетний, доля по ст. 81 остаётся правомерной."""
    config = DISABLED_CONFIG.replace("birthday: '01.01.2000'", "birthday: '01.01.2015'")
    config = config.replace("alimony_fixed: 20000", "alimony_percent: 20.0")
    assert not any("ст. 85 СК РФ" in note for note in calc(config).warnings)


def test_obligation_ends_early(calc):
    """Эмансипация: обязательство прекратилось задолго до 18 лет."""
    child = calc(EMANCIPATED_CONFIG).children[0]
    assert child.is_minor is True
    assert child.majority_date == datetime.date(2028, 6, 1)
    assert child.obligation_end == datetime.date(2026, 3, 1)
    assert child.ended_early is True
    assert child.obligation_active is False
    assert child.alimony_amount == Decimal("0.00")
    assert child.debt_payment == Decimal("40000.00")


def test_early_end_speeds_up_debt_repayment(calc):
    """
    До 01.03.2026 в долг уходило 15 000 (40 % минус текущий платёж 25 %),
    после прекращения обязательства — все 40 000.
    """
    mid = calc(EMANCIPATED_CONFIG, as_of=datetime.date(2026, 4, 1)).children[0]
    assert mid.months_paid == 3
    # 100000 - 15000 (01.02) - 40000 (01.03) - 40000 (01.04)
    assert mid.current_debt == Decimal("5000.00")

    child = calc(EMANCIPATED_CONFIG, as_of=datetime.date(2026, 5, 1)).children[0]
    assert child.months_paid == 4
    assert child.current_debt == Decimal("0.00")


def test_early_end_does_not_raise_withholding_limit(calc):
    """Ребёнок ещё несовершеннолетний, но алименты на него уже не взыскиваются."""
    result = calc(EMANCIPATED_CONFIG)
    assert result.children[0].raises_withholding_limit is False
    assert result.has_minor_children is False
    assert result.withholding_limit == Decimal("50")


def test_warns_about_early_termination(calc):
    result = calc(EMANCIPATED_CONFIG)
    note = next(n for n in result.warnings if "текущий платёж прекращён" in n)
    assert "01.03.2026" in note
    assert "прекращено досрочно (ст. 120 СК РФ)" in note


def test_early_end_makes_order_closable(calc):
    result = calc(EMANCIPATED_CONFIG, as_of=datetime.date(2027, 1, 1))
    child = result.children[0]
    assert child.is_closable is True
    assert any("обязательство прекращено и задолженности нет" in note for note in result.warnings)
    assert any("closed: true" in note for note in result.warnings)


def test_obligation_ended_after_majority_is_ignored(calc):
    """Дата позже совершеннолетия ничего не меняет — берётся более ранняя."""
    config = EMANCIPATED_CONFIG.replace("birthday: '01.06.2010'", "birthday: '01.06.2005'")
    child = calc(config).children[0]
    assert child.majority_date == datetime.date(2023, 6, 1)
    assert child.obligation_end == datetime.date(2023, 6, 1)
    assert child.ended_early is False


def test_disabled_with_early_termination(calc):
    """Усыновление прекращает обязательство даже перед нетрудоспособным ребёнком."""
    config = DISABLED_CONFIG.replace(
        "birthday: '01.01.2000'", "birthday: '01.01.2000'\n        obligation_ended: '01.05.2026'"
    )
    child = calc(config).children[0]
    assert child.obligation_end == datetime.date(2026, 5, 1)
    assert child.obligation_active is False
    assert child.alimony_amount == Decimal("0.00")
