"""Load a single AACT table into a pandas DataFrame, uniformly across backends.

One ``load_table`` call works whether AACT is installed as Postgres, SQLite,
a zip of pipe-delimited ``.txt`` files, a directory of ``.txt`` files, or a
directory of ``.csv`` files. Column projection (``columns``), row limiting
(``nrows``), equality filtering (``where``), and date parsing (``parse_dates``)
behave the same way on every backend.

Filtering note: for the DB backends the ``where`` filter is pushed down to SQL
(parameterized, injection-safe); for the file backends the table is read then
filtered in memory. For per-row hot loops against a file snapshot, read the
table once and filter the DataFrame yourself rather than calling ``load_table``
in a loop.
"""

from __future__ import annotations

import zipfile
from io import TextIOWrapper
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import pandas as pd

from .location import AACTBackend, AACTLocation, resolve_aact_location

# Date columns parsed by default per table (intersected with what's present).
# Pass ``parse_dates=False`` to disable, or an explicit list to override.
DEFAULT_DATE_COLUMNS: dict[str, list[str]] = {
    "studies": [
        "study_first_submitted_date",
        "results_first_submitted_date",
        "study_first_posted_date",
        "results_first_posted_date",
        "last_update_posted_date",
        "start_date",
        "verification_date",
        "completion_date",
        "primary_completion_date",
    ],
}

# Identifier-safe pattern for table/column names used in SQL string building.
import re as _re

_IDENT_RE = _re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _check_ident(name: str) -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return name


def _resolve_date_cols(
    table: str,
    parse_dates: Optional[Sequence[str] | bool],
    available: Optional[Iterable[str]],
) -> Optional[list[str]]:
    """Decide which columns to parse as dates."""
    if parse_dates is False:
        return None
    if parse_dates is None or parse_dates is True:
        cols = DEFAULT_DATE_COLUMNS.get(table, [])
    else:
        cols = list(parse_dates)
    if not cols:
        return None
    if available is not None:
        avail = set(available)
        cols = [c for c in cols if c in avail]
    return cols or None


def load_table(
    table: str,
    *,
    location: Optional[AACTLocation] = None,
    columns: Optional[Sequence[str]] = None,
    where: Optional[Mapping[str, object]] = None,
    nrows: Optional[int] = None,
    parse_dates: Optional[Sequence[str] | bool] = None,
) -> pd.DataFrame:
    """Load one AACT table.

    Parameters
    ----------
    table : str
        Table name without extension (e.g. ``"studies"``, ``"conditions"``).
    location : AACTLocation, optional
        Where AACT lives. Defaults to :func:`resolve_aact_location`.
    columns : sequence of str, optional
        Project to this column subset (reduces memory).
    where : mapping, optional
        Equality filter, e.g. ``{"nct_id": "NCT00000000"}``. Pushed to SQL for
        DB backends, applied in memory for file backends.
    nrows : int, optional
        Row limit (applied after filtering).
    parse_dates : sequence of str | bool, optional
        Columns to parse as datetimes. ``None`` uses
        :data:`DEFAULT_DATE_COLUMNS` for the table; ``False`` disables; a list
        overrides.

    Returns
    -------
    pandas.DataFrame
    """
    loc = location or resolve_aact_location()
    backend = loc.backend
    if backend is AACTBackend.TSV_DIR:
        return _load_delim_dir(loc, table, "|", ".txt", columns, where, nrows, parse_dates)
    if backend is AACTBackend.CSV_DIR:
        return _load_delim_dir(loc, table, ",", ".csv", columns, where, nrows, parse_dates)
    if backend is AACTBackend.ZIP:
        return _load_zip(loc, table, columns, where, nrows, parse_dates)
    if backend is AACTBackend.SQLITE:
        return _load_sqlite(loc, table, columns, where, nrows, parse_dates)
    if backend is AACTBackend.POSTGRES:
        return _load_postgres(loc, table, columns, where, nrows, parse_dates)
    raise ValueError(f"Unsupported backend: {backend}")


def _apply_where(df: pd.DataFrame, where: Optional[Mapping[str, object]]) -> pd.DataFrame:
    if not where:
        return df
    mask = pd.Series(True, index=df.index)
    for col, val in where.items():
        if col not in df.columns:
            raise KeyError(f"where column {col!r} not in table columns {list(df.columns)}")
        mask &= df[col].astype(str) == str(val)
    return df[mask]


def _read_delim(handle, sep, columns, nrows) -> pd.DataFrame:
    # Read dates as raw strings; date columns are coerced afterward via
    # _coerce_dates so a default date column that's absent from this particular
    # snapshot can't make read_csv raise (AACT's studies schema varies).
    return pd.read_csv(
        handle,
        sep=sep,
        usecols=list(columns) if columns is not None else None,
        nrows=nrows,
        parse_dates=False,
        low_memory=False,
    )


def _load_delim_dir(loc, table, sep, ext, columns, where, nrows, parse_dates) -> pd.DataFrame:
    path = loc.path / f"{table}{ext}"
    if not path.is_file():
        raise KeyError(
            f"Table {table!r} not found at {path}. "
            f"Available: {sorted(p.stem for p in loc.path.glob('*' + ext))}"
        )
    # When filtering, read all needed rows first (can't push down to a flat file),
    # so don't apply nrows until after the where-filter.
    read_nrows = None if where else nrows
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        df = _read_delim(f, sep, columns, read_nrows)
    df = _apply_where(df, where)
    if where and nrows is not None:
        df = df.head(nrows)
    df = _coerce_dates(df, table, parse_dates)
    return df.reset_index(drop=True)


def _load_zip(loc, table, columns, where, nrows, parse_dates) -> pd.DataFrame:
    filename = f"{table}.txt"
    read_nrows = None if where else nrows
    with zipfile.ZipFile(loc.dsn_or_path, "r") as zf:
        names = zf.namelist()
        match = [n for n in names if n.endswith(filename)]
        if not match:
            avail = sorted(
                n.split("/")[-1][:-4] for n in names if n.endswith(".txt")
            )
            raise KeyError(f"Table {table!r} not found in zip. Available: {avail}")
        # Prefer exact filename (e.g. "conditions.txt" over "browse_conditions.txt").
        exact = [n for n in match if n.split("/")[-1] == filename]
        target = exact[0] if exact else match[0]
        with zf.open(target) as f:
            df = _read_delim(TextIOWrapper(f, encoding="utf-8"), "|", columns, read_nrows)
    df = _apply_where(df, where)
    if where and nrows is not None:
        df = df.head(nrows)
    df = _coerce_dates(df, table, parse_dates)
    return df.reset_index(drop=True)


def _build_sql(table, columns, where, nrows, paramstyle):
    _check_ident(table)
    col_sql = ", ".join(_check_ident(c) for c in columns) if columns else "*"
    sql = f"SELECT {col_sql} FROM {table}"
    params: list[object] = []
    if where:
        placeholder = "?" if paramstyle == "qmark" else "%s"
        clauses = []
        for col, val in where.items():
            clauses.append(f"{_check_ident(col)} = {placeholder}")
            params.append(val)
        sql += " WHERE " + " AND ".join(clauses)
    if nrows is not None:
        sql += f" LIMIT {int(nrows)}"
    return sql, params


def _coerce_dates(df, table, parse_dates):
    date_cols = _resolve_date_cols(table, parse_dates, df.columns)
    if date_cols:
        for c in date_cols:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def _load_sqlite(loc, table, columns, where, nrows, parse_dates) -> pd.DataFrame:
    import sqlite3

    sql, params = _build_sql(table, columns, where, nrows, "qmark")
    conn = sqlite3.connect(loc.dsn_or_path)
    try:
        df = pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()
    return _coerce_dates(df, table, parse_dates)


def _load_postgres(loc, table, columns, where, nrows, parse_dates) -> pd.DataFrame:
    import psycopg2  # lazy: keeps psycopg2 an optional dependency

    sql, params = _build_sql(table, columns, where, nrows, "format")
    conn = psycopg2.connect(loc.dsn_or_path)
    try:
        df = pd.read_sql_query(sql, conn, params=params or None)
    finally:
        conn.close()
    return _coerce_dates(df, table, parse_dates)


def list_columns(table: str, location: Optional[AACTLocation] = None) -> list[str]:
    """Return the column names of *table* without loading the whole table."""
    loc = location or resolve_aact_location()
    backend = loc.backend
    if backend in (AACTBackend.TSV_DIR, AACTBackend.CSV_DIR, AACTBackend.ZIP):
        df = load_table(table, location=loc, nrows=0, parse_dates=False)
        return list(df.columns)
    if backend is AACTBackend.SQLITE:
        import sqlite3

        conn = sqlite3.connect(loc.dsn_or_path)
        try:
            cur = conn.execute(f"PRAGMA table_info({_check_ident(table)})")
            cols = [row[1] for row in cur.fetchall()]
        finally:
            conn.close()
        if not cols:  # PRAGMA returns empty (no error) for a nonexistent table
            raise KeyError(f"Table {table!r} not found in SQLite database")
        return cols
    if backend is AACTBackend.POSTGRES:
        import psycopg2

        conn = psycopg2.connect(loc.dsn_or_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s ORDER BY ordinal_position",
                (table,),
            )
            cols = [row[0] for row in cur.fetchall()]
        finally:
            conn.close()
        if not cols:  # empty information_schema result -> table absent
            raise KeyError(f"Table {table!r} not found in Postgres database")
        return cols
    raise ValueError(f"Unsupported backend: {backend}")


def table_exists(table: str, location: Optional[AACTLocation] = None) -> bool:
    """Whether *table* is available in this AACT location."""
    loc = location or resolve_aact_location()
    try:
        list_columns(table, location=loc)
        return True
    except (KeyError, FileNotFoundError):
        return False
    except Exception:
        # SQL backends raise backend-specific errors for a missing table.
        return False
