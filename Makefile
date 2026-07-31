.DEFAULT_GOAL := help
.PHONY: help install sync lock upgrade config run lint fmt fmt-check typecheck test cov check build clean

UV ?= uv
PKG := pyalimony
CONFIG := $(HOME)/.config/alimony.yaml

help:  ## Показать список целей
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: sync config  ## Полная подготовка окружения: зависимости + конфиг

sync:  ## Создать/обновить venv со всеми группами зависимостей
	$(UV) sync --all-groups

lock:  ## Пересобрать uv.lock
	$(UV) lock

upgrade:  ## Обновить зависимости до последних версий в рамках ограничений
	$(UV) lock --upgrade
	$(UV) sync --all-groups

config: $(CONFIG)  ## Положить пример конфига в ~/.config/alimony.yaml, если его нет

$(CONFIG): config.yaml
	@mkdir -p $(dir $(CONFIG))
	@cp config.yaml $(CONFIG)
	@echo "Конфиг создан: $(CONFIG)"

run: config  ## Запустить утилиту
	$(UV) run $(PKG)

lint:  ## Проверить код линтером
	$(UV) run ruff check .

fmt:  ## Отформатировать код и починить автофиксимые замечания
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

fmt-check:  ## Проверить форматирование без изменения файлов
	$(UV) run ruff format --check .

typecheck:  ## Проверить типы
	$(UV) run mypy $(PKG)/

test: config  ## Запустить тесты
	$(UV) run pytest

cov: config  ## Запустить тесты с отчётом о покрытии
	$(UV) run pytest --cov --cov-report=term-missing

check: lint fmt-check typecheck cov  ## Всё, что гоняет CI

build:  ## Собрать sdist и wheel
	$(UV) build

clean:  ## Удалить артефакты сборки и кеши
	rm -rf dist build .pytest_cache .ruff_cache .mypy_cache .coverage coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
