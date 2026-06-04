"""validate_columns: fail-closed on drift, project on success."""

from __future__ import annotations

import pandas as pd
import pytest

from aact_kit import AACTSchemaError, validate_columns


def _df():
    return pd.DataFrame([{"nct_id": "NCT1", "name": "X", "extra": "keep", "junk": "drop"}])


def test_passes_when_required_present():
    out = validate_columns(_df(), "conditions", required={"nct_id", "name"})
    assert set(out.columns) == {"name", "nct_id"}  # sorted, junk dropped


def test_keeps_optional_when_present():
    out = validate_columns(
        _df(), "conditions", required={"nct_id", "name"}, optional={"extra", "absent"}
    )
    assert set(out.columns) == {"extra", "name", "nct_id"}
    assert "absent" not in out.columns


def test_raises_on_missing_required():
    with pytest.raises(AACTSchemaError, match="missing required columns"):
        validate_columns(_df(), "conditions", required={"nct_id", "phase"})


def test_subset_false_returns_unchanged():
    df = _df()
    out = validate_columns(df, "conditions", required={"nct_id"}, subset=False)
    assert list(out.columns) == list(df.columns)


def test_column_sorted_output_is_stable():
    out = validate_columns(_df(), "conditions", required={"name", "nct_id"})
    assert list(out.columns) == sorted(out.columns)
