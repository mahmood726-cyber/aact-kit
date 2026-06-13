"""Collapse AACT's one-to-many child tables into per-trial list columns.

AACT stores conditions, interventions, facilities, sponsors, etc. as many rows
per ``nct_id``. Analyses almost always want one row per trial with the children
gathered into lists. ``aggregate_lists`` captures that groupby-sort-list pattern
once, with byte-stable (sorted) output, so callers don't re-implement it (and
re-introduce the ``sorted()`` TypeError on null/mixed values) each time.
"""

from __future__ import annotations

import pandas as pd


def aggregate_lists(
    df: pd.DataFrame,
    value_col: str,
    *,
    group_col: str = "nct_id",
    dedup: bool = True,
    sort: bool = True,
    name: str | None = None,
) -> pd.Series:
    """Group *df* by ``group_col`` and gather ``value_col`` into a list per group.

    NaN values are dropped and remaining values coerced to ``str`` before
    sorting, so mixed null/float/str columns (which real AACT has) don't crash
    ``sorted()``.

    Parameters
    ----------
    df : DataFrame
        A child table (e.g. conditions, interventions).
    value_col : str
        Column to gather into lists.
    group_col : str, default "nct_id"
        Grouping key.
    dedup : bool, default True
        Drop duplicate values within each group.
    sort : bool, default True
        Sort each list for byte-stable output.
    name : str, optional
        Name for the returned Series (defaults to ``value_col``).

    Returns
    -------
    Series
        Indexed by ``group_col``, each value a ``list[str]``.
    """
    for col in (group_col, value_col):
        if col not in df.columns:
            raise KeyError(f"column {col!r} not in DataFrame columns {list(df.columns)}")

    def _collapse(s: pd.Series) -> list[str]:
        vals_iter = s.dropna().astype(str)
        # Use dict.fromkeys to dedup while preserving insertion order, so that
        # dedup=True, sort=False gives a stable (first-seen) result instead of
        # the undefined iteration order of a set().
        if dedup:
            vals_iter = list(dict.fromkeys(vals_iter))
        else:
            vals_iter = list(vals_iter)
        return sorted(vals_iter) if sort else vals_iter

    out = df.groupby(group_col)[value_col].apply(_collapse)
    return out.rename(name or value_col)


def ensure_list_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Replace NaN with ``[]`` in the named list columns (post-merge cleanup).

    After a left-merge of aggregated list Series onto a studies table, trials
    with no children get float ``NaN`` instead of an empty list. This restores
    the empty-list invariant in place and returns *df*.
    """
    for col in columns:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: x if isinstance(x, list) else [])
    return df
