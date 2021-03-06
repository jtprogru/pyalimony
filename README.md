# pyalimony

![GitHub Workflow Status](https://img.shields.io/github/workflow/status/jtprogru/pyalimony/CI?label=CI)
![GitHub Workflow Status](https://img.shields.io/github/workflow/status/jtprogru/pyalimony/RELEASE?label=RELEASE)
![GitHub](https://img.shields.io/github/license/jtprogru/pyalimony)

Можно посчитать сколько осталось платить по алиментам

## Example
Пример входных данных, записанных в файл `~/.config/alimony.yaml`:

```yaml
---
SALARY: 1000000
# Рразмер удержаний по всем ИП
PERCENT: 70.0

childrens:
  - first_name: 'Иванов'
    second_name: 'Иван'
    middle_name: 'Михайловна'
    birthday: '30.11.2006'
    alimony:
      total_percent: 40.0
      alimony_percent: 25.0
      debt: 200000

  - first_name: 'Савин'
    second_name: 'Артём'
    middle_name: 'Михайлович'
    birthday: '08.05.2009'
    alimony:
      total_percent: 30.0
      alimony_percent: 16.6
      debt: 100000
```

## Development
Установка зависимостей и запуск:
```bash
poetry install
poetry run pyalimony
```
