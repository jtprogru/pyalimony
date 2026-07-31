# pyalimony

[![CI](https://github.com/jtprogru/pyalimony/actions/workflows/ci.yml/badge.svg)](https://github.com/jtprogru/pyalimony/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/jtprogru/pyalimony)](./LICENSE)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Консольная утилита: считает ежемесячный платёж по алиментам, платёж в счёт задолженности и сколько месяцев её ещё выплачивать.

## Установка

Нужен [uv](https://docs.astral.sh/uv/) и Python 3.14+.

```bash
git clone https://github.com/jtprogru/pyalimony.git
cd pyalimony
uv sync
```

## Конфигурация

Входные данные читаются из `~/.config/alimony.yaml`. За образец можно взять `config.yaml` из репозитория:

```bash
mkdir -p ~/.config && cp config.yaml ~/.config/alimony.yaml
```

```yaml
---
SALARY: 1000000        # зарплата на руки, в месяц
PERCENT: 70.0          # суммарный размер удержаний по всем ИП

childrens:
  - first_name: 'Иванов'
    second_name: 'Иван'
    middle_name: 'Михайловна'
    birthday: '30.11.2006'
    alimony:
      total_percent: 40.0     # весь удерживаемый процент по этому ИП
      alimony_percent: 25.0   # из них текущий платёж
      debt: 200000            # задолженность
```

Разница `total_percent - alimony_percent` уходит в погашение задолженности.

## Запуск

```bash
uv run pyalimony
```

## Разработка

```bash
make install   # venv с dev-зависимостями + конфиг в ~/.config
make check     # линт, форматирование, типы и тесты — то же, что гоняет CI
make help      # список всех целей
```

Без `make` то же самое напрямую:

```bash
uv sync --all-groups     # окружение вместе с dev-зависимостями
uv run ruff check .      # линт
uv run ruff format .     # форматирование
uv run mypy pyalimony/   # типы
uv run pytest --cov      # тесты
```

## Лицензия

[MIT](./LICENSE)
