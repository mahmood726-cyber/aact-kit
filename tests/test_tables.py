"""load_table / list_columns / table_exists behave identically across backends."""

from __future__ import annotations

import pandas as pd
import pytest

from aact_kit import list_columns, load_table, table_exists


def test_load_full_table(any_loc):
    df = load_table("studies", location=any_loc)
    assert len(df) == 3
    assert set(df["nct_id"]) == {"NCT1", "NCT2", "NCT3"}
    assert {"brief_title", "overall_status", "study_type"} <= set(df.columns)


def test_column_projection(any_loc):
    df = load_table("studies", location=any_loc, columns=["nct_id", "overall_status"])
    assert list(df.columns) == ["nct_id", "overall_status"]


def test_where_filter(any_loc):
    df = load_table("conditions", location=any_loc, where={"nct_id": "NCT1"})
    assert set(df["name"]) == {"Hypertension", "Diabetes"}
    assert len(df) == 2


def test_where_no_match_returns_empty(any_loc):
    df = load_table("conditions", location=any_loc, where={"nct_id": "NCT_NONE"})
    assert len(df) == 0


def test_nrows_limit(any_loc):
    df = load_table("studies", location=any_loc, nrows=2)
    assert len(df) == 2


def test_date_parsing_default(any_loc):
    df = load_table("studies", location=any_loc)
    assert pd.api.types.is_datetime64_any_dtype(df["start_date"])
    # NCT3 has an empty start_date -> NaT, not a crash.
    nct3 = df[df["nct_id"] == "NCT3"]["start_date"].iloc[0]
    assert pd.isna(nct3)


def test_date_parsing_disabled(any_loc):
    df = load_table("studies", location=any_loc, parse_dates=False)
    assert not pd.api.types.is_datetime64_any_dtype(df["start_date"])


def test_missing_table_raises(any_loc):
    with pytest.raises((KeyError, Exception)):
        load_table("no_such_table", location=any_loc)


def test_list_columns(any_loc):
    cols = list_columns("studies", location=any_loc)
    assert "nct_id" in cols and "brief_title" in cols


def test_table_exists(any_loc):
    assert table_exists("studies", location=any_loc) is True
    assert table_exists("definitely_not_a_table", location=any_loc) is False


def test_zip_member_under_subdir(zip_loc):
    # The zip stores members as export/<table>.txt; endswith match must find it.
    df = load_table("sponsors", location=zip_loc)
    assert len(df) == 3
