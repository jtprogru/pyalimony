"""
Нормативные константы и правила.

Каждая величина здесь взята из действующей нормы права, а не выдумана.
Расшифровка норм и ссылки на первоисточники — в docs/LEGAL.md.
"""

import datetime
from decimal import Decimal

# Возраст совершеннолетия. п. 1 ст. 21 ГК РФ.
# С его наступлением алиментные обязательства прекращаются — абз. 2 п. 2 ст. 120 СК РФ.
MAJORITY_AGE = 18

# Общий предел удержаний из зарплаты по исполнительным документам.
# ч. 2 ст. 99 ФЗ от 02.10.2007 № 229-ФЗ «Об исполнительном производстве».
BASE_WITHHOLDING_LIMIT = Decimal("50")

# Повышенный предел — применяется при взыскании алиментов на несовершеннолетних детей.
# ч. 3 ст. 99 ФЗ-229.
ALIMONY_WITHHOLDING_LIMIT = Decimal("70")

# Неустойка за просрочку уплаты алиментов, доля от суммы долга за каждый день.
# п. 2 ст. 115 СК РФ. Ставка 0,1 % действует с 10.08.2018, до этого была 0,5 %.
PENALTY_RATE_PER_DAY = Decimal("0.001")
PENALTY_RATE_PER_DAY_BEFORE = Decimal("0.005")
PENALTY_RATE_CHANGED_ON = datetime.date(2018, 8, 10)

# Сколько месяцев данные о задолженности считаются свежими.
# Задолженность определяет пристав (ст. 113 СК РФ), поэтому старый снимок нужно сверять.
DEBT_SNAPSHOT_STALE_AFTER_MONTHS = 6

# Допустимое отклонение от доли по ст. 81 СК РФ, процентных пунктов.
STATUTORY_SHARE_TOLERANCE = Decimal("0.5")


def statutory_share(children_count: int) -> Decimal:
    """
    Доля заработка, взыскиваемая на несовершеннолетних детей судом.

    п. 1 ст. 81 СК РФ: на одного ребёнка — 1/4, на двух — 1/3, на трёх и более — 1/2.
    Доля общая на всех детей плательщика, а не на каждого.

    :param children_count: количество несовершеннолетних детей
    :return: доля в процентах
    """
    if children_count <= 0:
        return Decimal("0")
    if children_count == 1:
        return Decimal("25")
    if children_count == 2:
        return Decimal("100") / Decimal("3")
    return Decimal("50")


def majority_date(birthday: datetime.date) -> datetime.date:
    """
    Дата совершеннолетия.

    :param birthday: дата рождения
    :return: дата, в которую ребёнку исполняется 18 лет
    """
    try:
        return birthday.replace(year=birthday.year + MAJORITY_AGE)
    except ValueError:
        # 29 февраля: в невисокосном году совершеннолетие наступает 28-го.
        return birthday.replace(year=birthday.year + MAJORITY_AGE, day=28)


def age_on(birthday: datetime.date, on: datetime.date) -> int:
    """
    Полных лет на дату.

    :param birthday: дата рождения
    :param on: дата, на которую считаем
    :return: количество полных лет
    """
    years = on.year - birthday.year
    if (on.month, on.day) < (birthday.month, birthday.day):
        years -= 1
    return years


def withholding_limit(has_minor_children: bool) -> Decimal:
    """
    Предельный процент удержания из дохода.

    :param has_minor_children: есть ли хотя бы одно ИП о взыскании алиментов
        на несовершеннолетнего ребёнка
    :return: предел в процентах (ч. 2-3 ст. 99 ФЗ-229)
    """
    return ALIMONY_WITHHOLDING_LIMIT if has_minor_children else BASE_WITHHOLDING_LIMIT
