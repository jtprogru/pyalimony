"""Тесты CLI и точки входа."""

import json
import runpy
import warnings

import pytest

import pyalimony
from pyalimony.main import build_parser, main
from tests.conftest import BASE_CONFIG, HISTORY_CONFIG


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


def test_help_lists_every_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for flag in ("--config", "--as-of", "--json", "--ledger", "--html", "--ledger-path", "--html-path"):
        assert flag in out


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


def test_ledger_flag_writes_csv(config_path, tmp_path, capsys):
    target = tmp_path / "out" / "ledger.csv"
    assert main(["--config", str(config_path), "--as-of", "31.07.2026", "--ledger", "--ledger-path", str(target)]) == 0
    assert target.exists()
    assert target.read_text(encoding="utf-8").startswith("month,child,")
    assert str(target) in capsys.readouterr().out


def test_html_flag_writes_report(config_path, tmp_path, capsys):
    target = tmp_path / "out" / "report.html"
    assert main(["--config", str(config_path), "--as-of", "31.07.2026", "--html", "--html-path", str(target)]) == 0
    assert target.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert str(target) in capsys.readouterr().out


def test_ledger_and_html_together(config_path, tmp_path, capsys):
    csv_path = tmp_path / "ledger.csv"
    html_path = tmp_path / "report.html"
    code = main(
        [
            "--config",
            str(config_path),
            "--as-of",
            "31.07.2026",
            "--ledger",
            "--ledger-path",
            str(csv_path),
            "--html",
            "--html-path",
            str(html_path),
        ]
    )
    assert code == 0
    assert csv_path.exists() and html_path.exists()
    out = capsys.readouterr().out
    assert "Выгрузка:" in out and "Отчёт:" in out
    assert "Расчёт на" not in out  # текстовый отчёт при этих флагах не печатается


def test_default_paths_follow_xdg(config_path, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert main(["--config", str(config_path), "--ledger", "--html"]) == 0
    assert (tmp_path / "data" / "alimony" / "ledger.csv").exists()
    assert (tmp_path / "data" / "alimony" / "report.html").exists()
    capsys.readouterr()


def test_unwritable_target_returns_error_code(config_path, tmp_path, capsys):
    blocker = tmp_path / "blocker"
    blocker.write_text("не каталог", encoding="utf-8")
    assert main(["--config", str(config_path), "--ledger", "--ledger-path", str(blocker / "ledger.csv")]) == 1
    assert "Ошибка записи" in capsys.readouterr().err


def test_text_report_still_default(config_path, capsys):
    assert main(["--config", str(config_path), "--as-of", "31.07.2026"]) == 0
    assert "Расчёт на 31.07.2026" in capsys.readouterr().out


def test_history_config_end_to_end(write_config, tmp_path, capsys):
    """Полный путь на конфиге с историей дохода и перерывом в работе."""
    path = write_config(HISTORY_CONFIG)
    html_path = tmp_path / "report.html"
    assert main(["--config", str(path), "--as-of", "31.07.2026", "--html", "--html-path", str(html_path)]) == 0
    page = html_path.read_text(encoding="utf-8")
    assert "апрель 2026" in page
    assert "без заработка 22 дн." in page
