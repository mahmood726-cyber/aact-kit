"""resolve_aact_location precedence and location_from_path inference."""

from __future__ import annotations

import pytest

from aact_kit import AACTBackend, location_from_path, resolve_aact_location
from aact_kit.location import _latest_dated_subdir


# --- env var precedence ------------------------------------------------------

_ENV_KEYS = ["AACT_DSN", "AACT_SQLITE", "AACT_ZIP", "AACT_TSV_DIR",
             "AACT_CSV_DIR", "AACT_SNAPSHOT_ROOTS"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)


def test_dsn_wins_first(monkeypatch, tmp_path):
    monkeypatch.setenv("AACT_DSN", "postgresql://u@localhost/aact")
    monkeypatch.setenv("AACT_TSV_DIR", str(tmp_path))
    loc = resolve_aact_location()
    assert loc.backend is AACTBackend.POSTGRES
    assert loc.dsn_or_path.endswith("/aact")


def test_tsv_dir_env(monkeypatch, tmp_path):
    monkeypatch.setenv("AACT_TSV_DIR", str(tmp_path))
    loc = resolve_aact_location()
    assert loc.backend is AACTBackend.TSV_DIR


def test_zip_env_requires_file(monkeypatch, tmp_path):
    missing = tmp_path / "nope.zip"
    monkeypatch.setenv("AACT_ZIP", str(missing))
    with pytest.raises(RuntimeError, match="does not exist"):
        resolve_aact_location()


def test_sqlite_env_requires_file(monkeypatch, tmp_path):
    monkeypatch.setenv("AACT_SQLITE", str(tmp_path / "absent.sqlite3"))
    with pytest.raises(RuntimeError, match="does not exist"):
        resolve_aact_location()


def test_fail_closed_when_nothing_set(monkeypatch):
    # Point discovery roots at an empty temp area so nothing is auto-found.
    monkeypatch.setenv("AACT_SNAPSHOT_ROOTS", "/nonexistent_root_aact_xyz")
    with pytest.raises(RuntimeError, match="AACT not found"):
        resolve_aact_location()


def test_auto_discovery_picks_latest_dated(monkeypatch, tmp_path):
    (tmp_path / "2024-01-01").mkdir()
    (tmp_path / "2026-05-10").mkdir()
    (tmp_path / "not-a-date").mkdir()
    monkeypatch.setenv("AACT_SNAPSHOT_ROOTS", str(tmp_path))
    loc = resolve_aact_location()
    assert loc.backend is AACTBackend.TSV_DIR
    assert loc.dsn_or_path.endswith("2026-05-10")


def test_latest_dated_subdir_none_when_empty(tmp_path):
    assert _latest_dated_subdir(str(tmp_path)) is None


# --- location_from_path ------------------------------------------------------

def test_from_path_zip(zip_loc):
    loc = location_from_path(zip_loc.dsn_or_path)
    assert loc.backend is AACTBackend.ZIP


def test_from_path_sqlite(sqlite_loc):
    loc = location_from_path(sqlite_loc.dsn_or_path)
    assert loc.backend is AACTBackend.SQLITE


def test_from_path_tsv_dir(tsv_dir):
    loc = location_from_path(tsv_dir.dsn_or_path)
    assert loc.backend is AACTBackend.TSV_DIR


def test_from_path_csv_dir(csv_dir):
    loc = location_from_path(csv_dir.dsn_or_path)
    assert loc.backend is AACTBackend.CSV_DIR


def test_from_path_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        location_from_path(tmp_path / "does_not_exist")
