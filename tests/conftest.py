"""Shared fixtures: generate the full six months once and run the pipeline on it, into a temp folder.

Building the data takes about half a minute, so it happens once per test session; the repo's own data/ is untouched.
"""
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from brewtower import generate, pipeline

MINI_RAW = Path(__file__).parent / "fixtures" / "mini_raw"


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    """Full synthetic dataset: raw files, DuckDB database and gold CSVs, plus pipeline.run's summary."""
    base = tmp_path_factory.mktemp("full")
    raw, db, gold = base / "raw", base / "brewtower.duckdb", base / "gold"
    generate.main(raw)
    result = pipeline.run(raw, db, gold)
    return SimpleNamespace(raw=raw, db=db, gold=gold, result=result)


@pytest.fixture
def con(built):
    """Read-only connection to the full build, closed after each test (so a test may re-run the pipeline)."""
    c = duckdb.connect(str(built.db), read_only=True)
    c.execute(f"""CREATE TEMP TABLE planted AS
                  SELECT source, CAST(file_date AS DATE) AS date, record_id, defect_type, dimension
                  FROM read_csv('{(built.raw / '_planted_defects.csv').as_posix()}', all_varchar = true)""")
    yield c
    c.close()


@pytest.fixture(scope="session")
def mini(tmp_path_factory):
    """The hand-made fixture in tests/fixtures/mini_raw, run through the pipeline."""
    base = tmp_path_factory.mktemp("mini")
    db, gold = base / "mini.duckdb", base / "gold"
    result = pipeline.run(MINI_RAW, db, gold)
    return SimpleNamespace(db=db, gold=gold, result=result)


@pytest.fixture
def mini_con(mini):
    c = duckdb.connect(str(mini.db), read_only=True)
    yield c
    c.close()
