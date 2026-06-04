"""Resolve where the local AACT data lives, across five backends.

AACT (Aggregate Analysis of ClinicalTrials.gov) can be installed locally in
several shapes. This module discovers which one is present and returns an
``AACTLocation`` describing it, without ever hardcoding a single drive.

Supported backends
-------------------
1. POSTGRES — a local PostgreSQL instance        (env: ``AACT_DSN``)
2. SQLITE   — a single-file SQLite snapshot       (env: ``AACT_SQLITE``)
3. ZIP      — a zip of pipe-delimited ``.txt``    (env: ``AACT_ZIP``)
4. TSV_DIR  — a dir of pipe-delimited ``.txt``    (env: ``AACT_TSV_DIR``)  [canonical bulk download]
5. CSV_DIR  — a dir of comma-delimited ``.csv``   (env: ``AACT_CSV_DIR``)

Resolution order (first hit wins):
    AACT_DSN -> AACT_SQLITE -> AACT_ZIP -> AACT_TSV_DIR -> AACT_CSV_DIR
    -> auto-discover most-recent ``YYYY-MM-DD`` snapshot dir under the roots
       in ``AACT_SNAPSHOT_ROOTS`` (os.pathsep-separated) or the built-in
       defaults -> fail closed with an actionable error.

Per the portfolio rule "Do not hardcode one drive": discovery roots are
configurable and include ``~/AACT`` so the default works regardless of the
Windows username.

AACT bulk downloads: https://aact.ctti-clinicaltrials.org/snapshots
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class AACTBackend(Enum):
    POSTGRES = "postgres"
    SQLITE = "sqlite"
    ZIP = "zip"          # zip archive of pipe-delimited .txt files
    TSV_DIR = "tsv_dir"  # pipe-delimited .txt files (AACT canonical local format)
    CSV_DIR = "csv_dir"  # comma-delimited .csv files (AACT CSV export variant)


@dataclass(frozen=True)
class AACTLocation:
    """Where AACT lives. ``dsn_or_path`` is a DSN for POSTGRES, else a path."""

    backend: AACTBackend
    dsn_or_path: str

    @property
    def path(self) -> Path:
        """The path for file/dir/zip backends (invalid for POSTGRES)."""
        if self.backend is AACTBackend.POSTGRES:
            raise ValueError("POSTGRES location has a DSN, not a filesystem path")
        return Path(self.dsn_or_path)


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Built-in discovery roots. Overridable via AACT_SNAPSHOT_ROOTS. ``~`` expands
# per-user so this works for any Windows username, not just one machine.
_DEFAULT_ROOTS = [
    "~/AACT",
    "C:/Users/user/AACT",     # legacy portfolio location
    "D:/AACT-storage/AACT",   # legacy portfolio location
]


def _discovery_roots() -> list[str]:
    env = os.environ.get("AACT_SNAPSHOT_ROOTS")
    roots = env.split(os.pathsep) if env else list(_DEFAULT_ROOTS)
    return [str(Path(r).expanduser()) for r in roots if r]


def _latest_dated_subdir(parent: str) -> Optional[Path]:
    """Most-recent ``YYYY-MM-DD`` subdirectory under *parent*, or None."""
    p = Path(parent)
    if not p.is_dir():
        return None
    dated = sorted(
        (d for d in p.iterdir() if d.is_dir() and _DATE_RE.match(d.name)),
        key=lambda d: d.name,
        reverse=True,
    )
    return dated[0] if dated else None


def location_from_path(path: str | os.PathLike) -> AACTLocation:
    """Infer a file-based backend from a concrete path.

    - ``*.zip``                       -> ZIP
    - ``*.sqlite``/``*.sqlite3``/``*.db`` -> SQLITE
    - a directory containing ``*.txt``    -> TSV_DIR
    - a directory containing only ``*.csv`` -> CSV_DIR

    Raises FileNotFoundError if the path does not exist, ValueError if the
    shape cannot be classified (e.g. an empty directory).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"AACT path does not exist: {p}")
    if p.is_file():
        suffix = p.suffix.lower()
        if suffix == ".zip":
            return AACTLocation(AACTBackend.ZIP, str(p))
        if suffix in (".sqlite", ".sqlite3", ".db"):
            return AACTLocation(AACTBackend.SQLITE, str(p))
        raise ValueError(f"Unrecognized AACT file type: {p.name}")
    # Directory: sniff for pipe-delimited .txt first (canonical), else .csv.
    if any(p.glob("*.txt")):
        return AACTLocation(AACTBackend.TSV_DIR, str(p))
    if any(p.glob("*.csv")):
        return AACTLocation(AACTBackend.CSV_DIR, str(p))
    raise ValueError(
        f"Directory {p} contains no .txt or .csv AACT tables to classify."
    )


def resolve_aact_location() -> AACTLocation:
    """Resolve the AACT location via env vars then snapshot auto-discovery.

    Raises RuntimeError with an actionable message if AACT is not found.
    """
    dsn = os.environ.get("AACT_DSN")
    if dsn:
        return AACTLocation(AACTBackend.POSTGRES, dsn)

    sqlite_env = os.environ.get("AACT_SQLITE")
    if sqlite_env:
        if not Path(sqlite_env).is_file():
            raise RuntimeError(f"AACT_SQLITE={sqlite_env!r} is set but file does not exist.")
        return AACTLocation(AACTBackend.SQLITE, sqlite_env)

    zip_env = os.environ.get("AACT_ZIP")
    if zip_env:
        if not Path(zip_env).is_file():
            raise RuntimeError(f"AACT_ZIP={zip_env!r} is set but file does not exist.")
        return AACTLocation(AACTBackend.ZIP, zip_env)

    tsv_env = os.environ.get("AACT_TSV_DIR")
    if tsv_env:
        if not Path(tsv_env).is_dir():
            raise RuntimeError(f"AACT_TSV_DIR={tsv_env!r} is set but directory does not exist.")
        return AACTLocation(AACTBackend.TSV_DIR, tsv_env)

    csv_env = os.environ.get("AACT_CSV_DIR")
    if csv_env:
        if not Path(csv_env).is_dir():
            raise RuntimeError(f"AACT_CSV_DIR={csv_env!r} is set but directory does not exist.")
        return AACTLocation(AACTBackend.CSV_DIR, csv_env)

    for root in _discovery_roots():
        subdir = _latest_dated_subdir(root)
        if subdir is not None:
            return AACTLocation(AACTBackend.TSV_DIR, str(subdir))

    raise RuntimeError(
        "AACT not found. Set one of:\n"
        "  AACT_DSN      - postgres DSN (e.g. postgresql://user@localhost/aact)\n"
        "  AACT_SQLITE   - path to a SQLite snapshot file\n"
        "  AACT_ZIP      - path to a zip of pipe-delimited .txt tables\n"
        "  AACT_TSV_DIR  - path to a directory of pipe-delimited .txt files\n"
        "  AACT_CSV_DIR  - path to a directory of comma-delimited .csv files\n"
        "Or place a snapshot under one of these roots as YYYY-MM-DD/ "
        "(auto-discovered, override with AACT_SNAPSHOT_ROOTS):\n"
        + "".join(f"    {r}\n" for r in _discovery_roots())
        + "AACT bulk downloads: https://aact.ctti-clinicaltrials.org/snapshots"
    )
