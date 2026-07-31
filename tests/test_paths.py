"""Тесты путей по спецификации XDG."""

from pathlib import Path

from pyalimony import paths


def test_config_path_default(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert paths.config_dir() == tmp_path / ".config" / "alimony"
    assert paths.config_path() == tmp_path / ".config" / "alimony" / "config.yaml"


def test_config_path_honours_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert paths.config_path() == tmp_path / "cfg" / "alimony" / "config.yaml"


def test_legacy_config_path(monkeypatch, tmp_path):
    """Прежнее расположение — файл прямо в ~/.config."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert paths.legacy_config_path() == tmp_path / ".config" / "alimony.yaml"


def test_data_paths_default(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert paths.data_dir() == tmp_path / ".local" / "share" / "alimony"
    assert paths.ledger_path() == tmp_path / ".local" / "share" / "alimony" / "ledger.csv"
    assert paths.report_path() == tmp_path / ".local" / "share" / "alimony" / "report.html"


def test_data_paths_honour_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert paths.data_dir() == tmp_path / "data" / "alimony"
    assert paths.ledger_path() == tmp_path / "data" / "alimony" / "ledger.csv"


def test_empty_xdg_var_falls_back_to_home(monkeypatch, tmp_path):
    """Пустая переменная равносильна отсутствующей."""
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert paths.config_dir() == tmp_path / ".config" / "alimony"
