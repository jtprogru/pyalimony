"""
Бизнес-логика расчёта.

Ключевая идея: остаток задолженности не выводится одной формулой, а моделируется
помесячно от даты постановления пристава. Так корректно отрабатывает переход через
Новый год и, главное, момент совершеннолетия — с ним текущий платёж прекращается
(абз. 2 п. 2 ст. 120 СК РФ), и всё удержание по ИП начинает уходить в долг.
"""

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from pyalimony import law
from pyalimony.config import ChildConfig, Config
from pyalimony.income import IncomeTimeline
from pyalimony.utils import (
    ZERO,
    add_months,
    format_date,
    format_money,
    format_percent,
    full_months_between,
    percent_of,
    plural,
    quantize_money,
)

# Предохранитель от бесконечного цикла, если долг не гасится.
_MAX_FORECAST_MONTHS = 1200


@dataclass(frozen=True, slots=True)
class Child:
    """
    Ребёнок с посчитанным на дату состоянием исполнительного производства.

    Все денежные величины — Decimal с точностью до копейки.
    """

    config: ChildConfig
    income: IncomeTimeline
    as_of: datetime.date

    @property
    def full_name(self) -> str:
        """ФИО одной строкой."""
        return self.config.full_name

    @property
    def birthday(self) -> datetime.date:
        """Дата рождения."""
        return self.config.birthday

    @property
    def majority_date(self) -> datetime.date:
        """Дата совершеннолетия (п. 1 ст. 21 ГК РФ)."""
        return law.majority_date(self.birthday)

    @property
    def age(self) -> int:
        """Полных лет на расчётную дату."""
        return law.age_on(self.birthday, self.as_of)

    @property
    def is_minor(self) -> bool:
        """Является ли ребёнок несовершеннолетним на расчётную дату."""
        return self.as_of < self.majority_date

    @property
    def is_closed(self) -> bool:
        """Прекращено ли исполнительное производство."""
        return self.config.alimony.closed

    @property
    def obligation_end(self) -> datetime.date | None:
        """
        Дата прекращения алиментного обязательства.

        Обычно это совершеннолетие (абз. 2 п. 2 ст. 120 СК РФ), но обязательство
        может прекратиться раньше — эмансипация, брак до 18 лет, усыновление
        ребёнка другим лицом. Для нетрудоспособного ребёнка обязательство
        бессрочно (ст. 85 СК РФ), тогда возвращается ``None``.
        """
        ended = self.config.obligation_ended
        if self.config.disabled:
            return ended
        if ended is None:
            return self.majority_date
        return min(ended, self.majority_date)

    @property
    def obligation_active(self) -> bool:
        """Действует ли алиментное обязательство на расчётную дату."""
        return self._obligation_active_on(self.as_of)

    @property
    def ended_early(self) -> bool:
        """Прекратилось ли обязательство раньше совершеннолетия."""
        ended = self.config.obligation_ended
        return ended is not None and ended < self.majority_date

    @property
    def raises_withholding_limit(self) -> bool:
        """
        Даёт ли это ИП основание для повышенного предела удержания.

        ч. 3 ст. 99 ФЗ-229 привязывает 70 % именно к взысканию алиментов
        на несовершеннолетних детей.
        """
        return self.is_minor and self.obligation_active

    @property
    def total_percent(self) -> Decimal:
        """Весь удерживаемый по ИП процент."""
        return self.config.alimony.total_percent

    @property
    def net_income(self) -> Decimal:
        """Доход за месяц расчётной даты."""
        return self.income.income_on(self.as_of)

    @property
    def started_at(self) -> datetime.date:
        """
        С какой даты по этому ИП взыскиваются алименты.

        Если в конфиге не указано, берётся начало истории дохода. Когда доход
        задан одним числом без дат, отсчёт ведётся от даты постановления пристава:
        раньше неё об этом ИП всё равно ничего не известно.
        """
        return self.config.alimony.started_at or self.income.start or self.debt_as_of

    @property
    def total_payment(self) -> Decimal:
        """Всё удержание по ИП за месяц расчётной даты."""
        return self.total_payment_on(self.as_of)

    def total_payment_on(self, day: datetime.date) -> Decimal:
        """
        Всё удержание по ИП за месяц, в который попадает дата.

        :param day: дата внутри интересующего месяца
        :return: сумма удержания за этот месяц
        """
        return percent_of(self.income.income_on(day), self.total_percent)

    @property
    def alimony_amount(self) -> Decimal:
        """
        Текущий платёж по алиментам на расчётную дату.

        После прекращения обязательства — ноль (ст. 120 СК РФ).
        """
        return self._alimony_on(self.as_of)

    @property
    def debt_payment(self) -> Decimal:
        """Сколько из удержания уходит в счёт задолженности на расчётную дату."""
        return self._debt_payment_on(self.as_of)

    @property
    def initial_debt(self) -> Decimal:
        """Задолженность на дату постановления пристава."""
        return self.config.alimony.debt

    @property
    def debt_as_of(self) -> datetime.date:
        """Дата, на которую известна задолженность (ст. 113 СК РФ)."""
        return self.config.alimony.debt_as_of

    @property
    def months_paid(self) -> int:
        """Сколько полных месяцев прошло с даты постановления пристава."""
        return full_months_between(self.debt_as_of, self.as_of)

    @property
    def current_debt(self) -> Decimal:
        """
        Остаток задолженности на расчётную дату.

        Не может уйти ниже нуля: переплата задолженностью не бывает.
        """
        return self._debt_after(self.months_paid)

    @property
    def months_left(self) -> int | None:
        """
        Сколько ещё месяцев гасить долг.

        ``None`` — долг не гасится: удержание в счёт задолженности равно нулю.
        ``0`` — долг уже закрыт.
        """
        debt = self.current_debt
        if debt <= ZERO:
            return 0
        month = self.months_paid
        for step in range(1, _MAX_FORECAST_MONTHS + 1):
            month += 1
            debt -= self._debt_payment_on(add_months(self.debt_as_of, month))
            if debt <= ZERO:
                return step
        return None

    @property
    def payoff_date(self) -> datetime.date | None:
        """Дата последнего платежа по задолженности, если она гасится."""
        months_left = self.months_left
        if months_left is None:
            return None
        return add_months(self.debt_as_of, self.months_paid + months_left)

    @property
    def is_closable(self) -> bool:
        """
        Можно ли прекращать исполнительное производство.

        Обязательство прекратилось и задолженности не осталось. Уже прекращённое
        производство сюда не попадает — прекращать нечего.
        """
        return not self.is_closed and not self.obligation_active and self.current_debt <= ZERO

    def _obligation_active_on(self, day: datetime.date) -> bool:
        """Действует ли алиментное обязательство на конкретную дату."""
        if self.is_closed:
            return False
        end = self.obligation_end
        return end is None or day < end

    def _alimony_on(self, day: datetime.date) -> Decimal:
        """Текущий платёж по алиментам на конкретную дату."""
        if not self._obligation_active_on(day):
            return ZERO
        order = self.config.alimony
        if order.alimony_fixed is not None:
            # Твёрдая сумма не может быть больше того, что вообще удерживается по ИП.
            return min(order.alimony_fixed, self.total_payment_on(day))
        if order.alimony_percent is None:  # pragma: no cover - валидация конфига этого не допускает
            return ZERO
        return percent_of(self.income.income_on(day), order.alimony_percent)

    def alimony_on(self, day: datetime.date) -> Decimal:
        """
        Текущий платёж по алиментам за месяц, в который попадает дата.

        :param day: дата внутри интересующего месяца
        :return: сумма текущего платежа
        """
        return self._alimony_on(day)

    def debt_payment_on(self, day: datetime.date) -> Decimal:
        """
        Платёж в счёт задолженности за месяц, в который попадает дата.

        :param day: дата внутри интересующего месяца
        :return: сумма, уходящая на погашение долга
        """
        return self._debt_payment_on(day)

    def _debt_payment_on(self, day: datetime.date) -> Decimal:
        """Платёж в счёт задолженности на конкретную дату."""
        return quantize_money(self.total_payment_on(day) - self._alimony_on(day))

    def _debt_after(self, months: int) -> Decimal:
        """Остаток задолженности после ``months`` ежемесячных удержаний."""
        debt = self.initial_debt
        for index in range(1, months + 1):
            if debt <= ZERO:
                return ZERO
            debt -= self._debt_payment_on(add_months(self.debt_as_of, index))
        return max(quantize_money(debt), ZERO)

    def __repr__(self) -> str:
        return f"<Child {self.full_name}, {self.birthday:%d.%m.%Y}, {self.age} лет>"


@dataclass(frozen=True, slots=True)
class Calculation:
    """
    Итог расчёта по всем исполнительным производствам.
    """

    as_of: datetime.date
    income: IncomeTimeline
    other_withholding_percent: Decimal
    children: tuple[Child, ...]
    warnings: tuple[str, ...] = field(default=())

    @property
    def alimony_percent(self) -> Decimal:
        """Суммарный процент удержаний по алиментным ИП."""
        return sum((child.total_percent for child in self.children), start=Decimal("0"))

    @property
    def alimony_withheld(self) -> Decimal:
        """Суммарное удержание по алиментным ИП за месяц."""
        return quantize_money(sum((child.total_payment for child in self.children), start=ZERO))

    @property
    def net_income(self) -> Decimal:
        """Доход за месяц расчётной даты."""
        return self.income.income_on(self.as_of)

    @property
    def income_kind(self) -> str:
        """Как получен доход расчётного месяца: зарплата, средняя, смешанно, факт."""
        return self.income.income_for_month(self.as_of.year, self.as_of.month).kind

    @property
    def other_withheld(self) -> Decimal:
        """Удержание по неалиментным ИП за месяц."""
        return percent_of(self.net_income, self.other_withholding_percent)

    @property
    def total_withheld_percent(self) -> Decimal:
        """Суммарный процент удержаний по всем ИП."""
        return self.alimony_percent + self.other_withholding_percent

    @property
    def total_withheld(self) -> Decimal:
        """Суммарное удержание за месяц."""
        return quantize_money(self.alimony_withheld + self.other_withheld)

    @property
    def take_home(self) -> Decimal:
        """Сколько остаётся на руки после всех удержаний."""
        return quantize_money(self.net_income - self.total_withheld)

    @property
    def has_minor_children(self) -> bool:
        """
        Взыскиваются ли алименты хотя бы на одного несовершеннолетнего ребёнка.

        Именно это, а не сам факт наличия несовершеннолетних детей, даёт
        повышенный предел удержания по ч. 3 ст. 99 ФЗ-229.
        """
        return any(child.raises_withholding_limit for child in self.children)

    @property
    def withholding_limit(self) -> Decimal:
        """Предельный процент удержания по ч. 2-3 ст. 99 ФЗ-229."""
        return law.withholding_limit(self.has_minor_children)

    @property
    def total_debt(self) -> Decimal:
        """Суммарный остаток задолженности по всем ИП."""
        return quantize_money(sum((child.current_debt for child in self.children), start=ZERO))


def calculate(config: Config, as_of: datetime.date | None = None) -> Calculation:
    """
    Посчитать состояние всех исполнительных производств на дату.

    :param config: разобранный конфиг
    :param as_of: расчётная дата, по умолчанию сегодня
    :return: результат расчёта вместе с предупреждениями
    """
    day = as_of or datetime.date.today()
    children = tuple(Child(config=child, income=config.income, as_of=day) for child in config.children)
    return Calculation(
        as_of=day,
        income=config.income,
        other_withholding_percent=config.other_withholding_percent,
        children=children,
        warnings=tuple(check_compliance(children, config.other_withholding_percent, day)),
    )


def check_compliance(
    children: tuple[Child, ...],
    other_withholding_percent: Decimal,
    as_of: datetime.date,
) -> list[str]:
    """
    Проверить расчёт на соответствие нормам и собрать предупреждения.

    Это не блокирующие ошибки: конфиг может описывать фактическое положение дел,
    даже если оно спорно. Задача — показать, где оно расходится с законом.

    :param children: посчитанные дети
    :param other_withholding_percent: удержания по неалиментным ИП
    :param as_of: расчётная дата
    :return: список предупреждений
    """
    notes: list[str] = []
    # Повышенный предел даёт только действующее взыскание на несовершеннолетнего:
    # прекращённое обязательство и алименты по ст. 85 СК РФ основанием не являются.
    minors = [child for child in children if child.raises_withholding_limit]
    total_percent = sum((child.total_percent for child in children), start=Decimal("0"))
    total_percent += other_withholding_percent
    limit = law.withholding_limit(bool(minors))

    if total_percent > limit:
        notes.append(
            f"Суммарное удержание {format_percent(total_percent)} превышает предел "
            f"{format_percent(limit)} ({'ч. 3' if minors else 'ч. 2'} ст. 99 ФЗ-229)."
        )
    if not minors and total_percent > law.BASE_WITHHOLDING_LIMIT:
        notes.append(
            "Действующих алиментов на несовершеннолетних детей нет: повышенный предел 70 % "
            "установлен именно для них (ч. 3 ст. 99 ФЗ-229), и удержание свыше 50 % "
            "стоит уточнить у пристава."
        )

    notes.extend(_check_statutory_share(minors))

    for child in children:
        notes.extend(_check_child(child, as_of))

    if any(child.current_debt > ZERO for child in children):
        notes.append(
            "На задолженность может быть начислена неустойка 0,1 % за каждый день просрочки "
            "(п. 2 ст. 115 СК РФ). В расчёт она не входит."
        )
    return notes


def _check_statutory_share(minors: list[Child]) -> list[str]:
    """Сверить назначенные доли с п. 1 ст. 81 СК РФ."""
    if not minors:
        return []
    percent_based = [child for child in minors if child.config.alimony.alimony_percent is not None]
    if len(percent_based) != len(minors):
        # В твёрдой сумме доли не сравниваются.
        return []
    assigned = sum(
        (child.config.alimony.alimony_percent or Decimal("0") for child in percent_based),
        start=Decimal("0"),
    )
    expected = law.statutory_share(len(minors))
    if abs(assigned - expected) <= law.STATUTORY_SHARE_TOLERANCE:
        return []
    direction = "выше" if assigned > expected else "ниже"
    count = len(minors)
    word = plural(count, "ребёнка", "детей", "детей")
    return [
        f"Суммарный текущий платёж по несовершеннолетним детям {format_percent(assigned)} "
        f"{direction} доли {format_percent(expected)} на {count} {word} по п. 1 ст. 81 СК РФ. "
        f"Основание для пересмотра размера (п. 2 ст. 81, ст. 119 СК РФ)."
    ]


def _check_child(child: Child, as_of: datetime.date) -> list[str]:
    """Проверки по отдельному ИП."""
    if child.is_closed:
        # Прекращённое производство в расчёте не участвует, замечаний по нему нет.
        return []

    notes: list[str] = []
    name = child.full_name

    if child.config.disabled and not child.is_minor and child.config.alimony.alimony_percent is not None:
        notes.append(
            f"{name}: алименты на нетрудоспособного совершеннолетнего ребёнка взыскиваются "
            f"в твёрдой денежной сумме (п. 2 ст. 85 СК РФ), а не долей заработка. "
            f"Используйте alimony_fixed вместо alimony_percent."
        )
    if child.is_closable and child.total_percent > ZERO:
        reason = "обязательство прекращено" if child.ended_early else "ребёнок совершеннолетний"
        notes.append(
            f"{name}: {reason} и задолженности нет, но по ИП удерживается "
            f"{format_percent(child.total_percent)}. Производство подлежит прекращению "
            f"(ст. 120 СК РФ, п. 9 ч. 2 ст. 43 ФЗ-229). Отметьте его в конфиге как closed: true."
        )
    if child.current_debt > ZERO and child.debt_payment <= ZERO:
        notes.append(
            f"{name}: задолженность {format_money(child.current_debt)} руб. не гасится — "
            f"весь удерживаемый процент уходит на текущий платёж."
        )
    stale_after = add_months(child.debt_as_of, law.DEBT_SNAPSHOT_STALE_AFTER_MONTHS)
    if child.initial_debt > ZERO and as_of > stale_after:
        notes.append(
            f"{name}: данные о задолженности от {format_date(child.debt_as_of)} старше "
            f"{law.DEBT_SNAPSHOT_STALE_AFTER_MONTHS} месяцев. Сверьтесь с постановлением "
            f"пристава о расчёте задолженности (ст. 113 СК РФ)."
        )
    end = child.obligation_end
    if end is not None and not child.obligation_active and end > child.debt_as_of:
        basis = (
            "обязательство прекращено досрочно (ст. 120 СК РФ)"
            if child.ended_early
            else "по достижении 18 лет (абз. 2 п. 2 ст. 120 СК РФ)"
        )
        notes.append(
            f"{name}: текущий платёж прекращён {format_date(end)} — {basis}, "
            f"дальше удержание идёт только в счёт задолженности."
        )
    return notes
