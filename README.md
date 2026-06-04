# aact-kit

Unified local-AACT data access for the ClinicalTrials.gov portfolio. One small
API to **resolve** where AACT lives, **load** any table, **validate** its
schema, and **collapse** child tables to per-trial lists — identically across
five local backends.

AACT (Aggregate Analysis of ClinicalTrials.gov) is the CTTI relational mirror
of CT.gov. Locally it shows up in several shapes; `aact-kit` hides the
differences so analysis code doesn't re-implement the plumbing (and re-discover
the same bugs) in every project.

## Supported backends

| Backend | Shape | Env var |
|---|---|---|
| `POSTGRES` | local PostgreSQL instance | `AACT_DSN` |
| `SQLITE` | single-file snapshot | `AACT_SQLITE` |
| `ZIP` | zip of pipe-delimited `.txt` | `AACT_ZIP` |
| `TSV_DIR` | dir of pipe-delimited `.txt` (canonical bulk download) | `AACT_TSV_DIR` |
| `CSV_DIR` | dir of comma-delimited `.csv` | `AACT_CSV_DIR` |

## Install

```bash
pip install aact-kit               # once published to PyPI
pip install -e path/to/aact-kit    # local editable, until then
pip install "aact-kit[postgres]"   # add psycopg2 for the Postgres backend
```

## Quick start

```python
from aact_kit import load_table, resolve_aact_location

loc = resolve_aact_location()                     # discover via env / snapshot dir
studies = load_table("studies", location=loc)     # full table, dates parsed
us = load_table("countries", location=loc,
                where={"nct_id": "NCT00000000"},   # equality filter (SQL push-down on DB)
                columns=["name", "removed"])
```

Point at a concrete path instead of discovery:

```python
from aact_kit import load_table, location_from_path

loc = location_from_path("/data/aact/20260219_export.zip")   # backend inferred
df = load_table("studies", location=loc, nrows=1000)
```

### Resolution order

`resolve_aact_location()` checks, first hit wins:

```
AACT_DSN -> AACT_SQLITE -> AACT_ZIP -> AACT_TSV_DIR -> AACT_CSV_DIR
         -> most-recent YYYY-MM-DD snapshot dir under AACT_SNAPSHOT_ROOTS
            (or the built-in roots, including ~/AACT)
         -> RuntimeError with an actionable message
```

No drive is hardcoded: discovery roots are configurable via
`AACT_SNAPSHOT_ROOTS` (os.pathsep-separated) and include `~/AACT`.

## API

| Function | Purpose |
|---|---|
| `resolve_aact_location()` | Discover the AACT backend from env / snapshot dirs |
| `location_from_path(path)` | Infer a backend from a concrete file/dir |
| `load_table(table, *, location, columns, where, nrows, parse_dates)` | Load one table |
| `list_columns(table, location)` | Column names without loading rows |
| `table_exists(table, location)` | Availability check |
| `validate_columns(df, table, required, optional, *, subset)` | Fail-closed schema check |
| `aggregate_lists(df, value_col, *, group_col, dedup, sort, name)` | Collapse a child table to per-trial lists |
| `ensure_list_columns(df, columns)` | Replace post-merge `NaN` with `[]` |

`load_table` parses known date columns (`DEFAULT_DATE_COLUMNS`) automatically;
pass `parse_dates=False` to disable or a list to override.

## Design notes

- **Domain logic stays in the consuming project.** `aact-kit` is the data-access
  layer (resolve / load / validate / aggregate). Project-specific queries
  (country lists, effect-size extraction, condition filtering) build on top of it.
- **Fail closed.** Missing tables raise `KeyError`; missing required columns raise
  `AACTSchemaError`; an unresolvable location raises `RuntimeError` with the exact
  env vars to set.
- **Byte-stable.** `aggregate_lists` sorts and de-dups so output doesn't drift with
  AACT's row order between quarterly releases.
- **psycopg2 is optional.** The Postgres backend imports it lazily, so the library
  works without it for the file/SQLite backends.

AACT bulk downloads: <https://aact.ctti-clinicaltrials.org/snapshots>

## License

MIT
