"""Build the same tiny AACT dataset in every file-based backend, once per session.

A single 3-trial dataset is materialized as a TSV dir, a CSV dir, a zip of
pipe-delimited .txt files, and a SQLite db, so backend-parametrized tests can
assert identical behavior across all of them.
"""

from __future__ import annotations

import sqlite3
import zipfile

import pandas as pd
import pytest

from aact_kit import AACTBackend, AACTLocation

# One small, deterministic dataset. Child tables are intentionally one-to-many
# and include a trial (NCT3) with no conditions/facilities to exercise empties.
TABLES: dict[str, list[dict]] = {
    "studies": [
        {"nct_id": "NCT1", "brief_title": "Alpha trial", "start_date": "2020-01-15",
         "enrollment": "120", "overall_status": "Completed", "study_type": "Interventional"},
        {"nct_id": "NCT2", "brief_title": "Beta trial", "start_date": "2021-06-01",
         "enrollment": "80", "overall_status": "Recruiting", "study_type": "Interventional"},
        {"nct_id": "NCT3", "brief_title": "Gamma trial", "start_date": "",
         "enrollment": "", "overall_status": "Withdrawn", "study_type": "Observational"},
    ],
    "conditions": [
        {"nct_id": "NCT1", "name": "Hypertension"},
        {"nct_id": "NCT1", "name": "Diabetes"},
        {"nct_id": "NCT2", "name": "Asthma"},
    ],
    "interventions": [
        {"nct_id": "NCT1", "intervention_type": "drug", "name": "DrugA"},
        {"nct_id": "NCT1", "intervention_type": "drug", "name": "DrugA"},  # dup on purpose
        {"nct_id": "NCT2", "intervention_type": "biological", "name": "BioB"},
    ],
    "facilities": [
        {"nct_id": "NCT1", "country": "United States", "city": "Boston"},
        {"nct_id": "NCT1", "country": "Canada", "city": "Toronto"},
        {"nct_id": "NCT2", "country": "United States", "city": "Austin"},
    ],
    "sponsors": [
        {"nct_id": "NCT1", "lead_or_collaborator": "lead", "name": "Acme"},
        {"nct_id": "NCT1", "lead_or_collaborator": "collaborator", "name": "Helper Inc"},
        {"nct_id": "NCT2", "lead_or_collaborator": "lead", "name": "Beta Labs"},
    ],
    "countries": [
        {"id": "1", "nct_id": "NCT1", "name": "United States", "removed": "f"},
        {"id": "2", "nct_id": "NCT1", "name": "Canada", "removed": "f"},
        {"id": "3", "nct_id": "NCT1", "name": "Mexico", "removed": "t"},  # removed -> excluded
        {"id": "4", "nct_id": "NCT2", "name": "United States", "removed": "f"},
    ],
}


def _frames() -> dict[str, pd.DataFrame]:
    return {name: pd.DataFrame(rows) for name, rows in TABLES.items()}


@pytest.fixture(scope="session")
def tsv_dir(tmp_path_factory) -> AACTLocation:
    d = tmp_path_factory.mktemp("aact_tsv")
    for name, df in _frames().items():
        df.to_csv(d / f"{name}.txt", sep="|", index=False)
    return AACTLocation(AACTBackend.TSV_DIR, str(d))


@pytest.fixture(scope="session")
def csv_dir(tmp_path_factory) -> AACTLocation:
    d = tmp_path_factory.mktemp("aact_csv")
    for name, df in _frames().items():
        df.to_csv(d / f"{name}.csv", sep=",", index=False)
    return AACTLocation(AACTBackend.CSV_DIR, str(d))


@pytest.fixture(scope="session")
def zip_loc(tmp_path_factory) -> AACTLocation:
    d = tmp_path_factory.mktemp("aact_zip")
    zpath = d / "aact_export.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        for name, df in _frames().items():
            # Place under a subdir to exercise the endswith() member match.
            zf.writestr(f"export/{name}.txt", df.to_csv(sep="|", index=False))
    return AACTLocation(AACTBackend.ZIP, str(zpath))


@pytest.fixture(scope="session")
def sqlite_loc(tmp_path_factory) -> AACTLocation:
    d = tmp_path_factory.mktemp("aact_sqlite")
    dbpath = d / "aact.sqlite3"
    conn = sqlite3.connect(dbpath)
    try:
        for name, df in _frames().items():
            df.to_sql(name, conn, index=False, if_exists="replace")
    finally:
        conn.close()
    return AACTLocation(AACTBackend.SQLITE, str(dbpath))


@pytest.fixture(params=["tsv", "csv", "zip", "sqlite"])
def any_loc(request) -> AACTLocation:
    """Every file-based backend, one at a time."""
    return request.getfixturevalue({
        "tsv": "tsv_dir", "csv": "csv_dir", "zip": "zip_loc", "sqlite": "sqlite_loc",
    }[request.param])
