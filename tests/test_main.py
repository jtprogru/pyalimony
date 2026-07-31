"""Тесты CLI и точки входа."""

import json
import runpy
import warnings

import pytest

import pyalimony
from pyalimony.main import build_parser, main
from tests.conftest import BASE_CONFIG


@pytest.fixture
def config_path(write_config):
    return write_config(BASE_CONFIG)


def test_prints_report(config_path, capsys):
    assert main(["--config", str(config_path), "--as-of", "31.07.2026"]) == 0
    out = capsys.readouterr().out
    assert "Расчёт на 31.07.2026" in out
    assert "Иванов Иван Иванович" in out
    assert "Петров Пётр Петрович" in out


def test_json_output(config_path, capsys):
    assert main(["--config", str(config_path), "--as-of", "31.07.2026", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["take_home"] == 30000.0
    assert len(data["children"]) == 2


def test_short_config_flag(config_path, capsys):
    assert main(["-c", str(config_path)]) == 0
    assert "Расчёт на" in capsys.readouterr().out


def test_as_of_defaults_to_today(config_path, capsys):
    import datetime

    assert main(["--config", str(config_path)]) == 0
    assert f"Расчёт на {datetime.date.today():%d.%m.%Y}" in capsys.readouterr().out


def test_iso_as_of_accepted(config_path, capsys):
    assert main(["--config", str(config_path), "--as-of", "2026-07-31"]) == 0
    assert "Расчёт на 31.07.2026" in capsys.readouterr().out


def test_missing_config_returns_error_code(tmp_path, capsys):
    assert main(["--config", str(tmp_path / "нет.yaml")]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Конфиг не найден" in captured.err


def test_invalid_config_returns_error_code(write_config, capsys):
    path = write_config(BASE_CONFIG.replace("net_income: 100000", "net_income: -5"))
    assert main(["--config", str(path)]) == 1
    assert "доход должен быть положительным" in capsys.readouterr().err


def test_bad_as_of_returns_error_code(config_path, capsys):
    assert main(["--config", str(config_path), "--as-of", "вчера"]) == 1
    assert "--as-of" in capsys.readouterr().err


def test_help_mentions_default_config_path(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "alimony.yaml" in capsys.readouterr().out


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.config is None
    assert args.as_of is None
    assert args.json is False


def test_module_run_as_script(monkeypatch, config_path, capsys):
    """Ветка ``if __name__ == "__main__"``."""
    monkeypatch.setattr("sys.argv", ["pyalimony", "--config", str(config_path)])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("pyalimony.main", run_name="__main__")
    assert exc.value.code == 0
    assert "Расчёт на" in capsys.readouterr().out


def test_package_exports():
    assert callable(pyalimony.main)
    assert callable(pyalimony.calculate)
    assert callable(pyalimony.load_config)
    assert "ConfigError" in pyalimony.__all__


def test_importing_package_does_not_read_config(monkeypatch, tmp_path):
    """
    Регрессия: раньше конфиг читался на этапе импорта, и пакет было не импортировать
    без ~/.config/alimony.yaml. Теперь загрузка только явная.
    """
    import importlib
    from pathlib import Path

    nowhere = tmp_path / "дома-нет"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: nowhere))
    for name in ("pyalimony.config", "pyalimony.struct", "pyalimony.reports", "pyalimony.main", "pyalimony"):
        importlib.reload(importlib.import_module(name))
