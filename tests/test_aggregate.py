"""aggregate_lists / ensure_list_columns collapse semantics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aact_kit import aggregate_lists, ensure_list_columns


def test_dedup_and_sort():
    df = pd.DataFrame([
        {"nct_id": "NCT1", "name": "DrugB"},
        {"nct_id": "NCT1", "name": "DrugA"},
        {"nct_id": "NCT1", "name": "DrugA"},  # dup
        {"nct_id": "NCT2", "name": "DrugC"},
    ])
    out = aggregate_lists(df, "name")
    assert out["NCT1"] == ["DrugA", "DrugB"]
    assert out["NCT2"] == ["DrugC"]


def test_no_dedup_keeps_duplicates():
    df = pd.DataFrame([
        {"nct_id": "NCT1", "name": "X"},
        {"nct_id": "NCT1", "name": "X"},
    ])
    out = aggregate_lists(df, "name", dedup=False)
    assert out["NCT1"] == ["X", "X"]


def test_nan_values_dropped_not_crash():
    # Mixed null/str would crash a naive sorted(); aggregate must coerce+drop.
    df = pd.DataFrame([
        {"nct_id": "NCT1", "name": "Real"},
        {"nct_id": "NCT1", "name": np.nan},
    ])
    out = aggregate_lists(df, "name")
    assert out["NCT1"] == ["Real"]


def test_series_name_defaults_to_value_col():
    df = pd.DataFrame([{"nct_id": "NCT1", "country": "US"}])
    out = aggregate_lists(df, "country")
    assert out.name == "country"


def test_custom_series_name():
    df = pd.DataFrame([{"nct_id": "NCT1", "country": "US"}])
    out = aggregate_lists(df, "country", name="countries")
    assert out.name == "countries"


def test_missing_column_raises():
    df = pd.DataFrame([{"nct_id": "NCT1"}])
    with pytest.raises(KeyError):
        aggregate_lists(df, "name")


def test_ensure_list_columns_fills_nan():
    df = pd.DataFrame({"nct_id": ["NCT1", "NCT2"], "conditions": [["A"], np.nan]})
    out = ensure_list_columns(df, ["conditions"])
    assert out.loc[1, "conditions"] == []
    assert out.loc[0, "conditions"] == ["A"]
