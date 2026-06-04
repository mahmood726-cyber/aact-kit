"""aact-kit — unified local-AACT (ClinicalTrials.gov) data access.

Resolve where AACT lives, load any table, validate its schema, and collapse
child tables to per-trial lists — identically across five local backends
(Postgres, SQLite, zip, pipe-delimited TSV dir, comma-delimited CSV dir).

Quick start
-----------
    from aact_kit import load_table, resolve_aact_location

    loc = resolve_aact_location()                  # discovers AACT via env/snapshot
    studies = load_table("studies", location=loc)  # one row per study

Or point at a concrete path:

    from aact_kit import load_table, location_from_path
    loc = load_table("studies", location=location_from_path("/data/aact.zip"))
"""

from __future__ import annotations

from .aggregate import aggregate_lists, ensure_list_columns
from .location import (
    AACTBackend,
    AACTLocation,
    location_from_path,
    resolve_aact_location,
)
from .schema import AACTSchemaError, validate_columns
from .tables import (
    DEFAULT_DATE_COLUMNS,
    list_columns,
    load_table,
    table_exists,
)

__version__ = "0.1.0"

__all__ = [
    "AACTBackend",
    "AACTLocation",
    "resolve_aact_location",
    "location_from_path",
    "load_table",
    "list_columns",
    "table_exists",
    "DEFAULT_DATE_COLUMNS",
    "validate_columns",
    "AACTSchemaError",
    "aggregate_lists",
    "ensure_list_columns",
    "__version__",
]
