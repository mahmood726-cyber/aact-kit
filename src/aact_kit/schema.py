"""Fail-closed schema validation for AACT tables.

AACT's schema drifts between quarterly releases. Rather than silently produce
wrong output when an expected column disappears, validate up front and raise.
This mirrors the per-project pattern (e.g. africa-tb-atlas's ``REQUIRED_SCHEMAS``)
so every consumer fails the same, loud way.
"""

from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd


class AACTSchemaError(Exception):
    """Raised when an AACT table is missing required columns (schema drift)."""


def validate_columns(
    df: pd.DataFrame,
    table: str,
    required: Iterable[str],
    optional: Optional[Iterable[str]] = None,
    *,
    subset: bool = True,
) -> pd.DataFrame:
    """Validate that *df* has all *required* columns; optionally project it.

    Parameters
    ----------
    df : DataFrame
        A loaded AACT table.
    table : str
        Table name, used only for error messages.
    required : iterable of str
        Columns that must be present. Missing any -> :class:`AACTSchemaError`.
    optional : iterable of str, optional
        Extra columns to keep when present (ignored when absent).
    subset : bool, default True
        If True, return ``df`` projected to ``required | (optional & present)``,
        column-sorted for byte-stable output. If False, return ``df`` unchanged
        after validation.

    Returns
    -------
    DataFrame
    """
    required = set(required)
    optional = set(optional or ())
    actual = set(df.columns)
    missing = required - actual
    if missing:
        raise AACTSchemaError(
            f"{table} missing required columns: {sorted(missing)}. "
            f"AACT schema may have drifted; re-audit and update the required set."
        )
    if not subset:
        return df
    keep = (required | optional) & actual
    return df[sorted(keep)]
