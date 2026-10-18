"""Tests for the synthetic data generator: run with `pytest`.

The generator is the ground truth for everything else, so: same seed -> same files, a well-formed answer key,
and the planted incidents (carrier outage in May, Brno feed stop in August) really in the files.
"""
import hashlib
from datetime import date, timedelta

import duckdb

from brewtower import generate

SOURCES = {"erp_orders", "wms_shipments", "carrier_tracking", "master_data"}
DIMENSIONS = {"completeness", "validity", "freshness"}


def tree_hash(root):
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        h.update(path.relative_to(root).as_posix().encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def raw(built, folder):
    """All files of one feed as one table, with the file's date."""
    return (f"(SELECT *, CAST(regexp_extract(filename, '(\\d{{4}}-\\d{{2}}-\\d{{2}})\\.csv$', 1) AS DATE) AS file_date "
            f"FROM read_csv('{(built.raw / folder).as_posix()}/[0-9]*.csv', all_varchar = true, filename = true))")


def test_same_seed_same_files(built, tmp_path):
    generate.main(tmp_path / "raw")
    assert tree_hash(tmp_path / "raw") == tree_hash(built.raw)   # every file, byte for byte


def test_answer_key_schema(built):
    con = duckdb.connect()
    key = con.execute(f"SELECT * FROM read_csv('{(built.raw / '_planted_defects.csv').as_posix()}', all_varchar = true)")
    assert [c[0] for c in key.description] == ["source", "file_date", "record_id", "defect_type", "dimension",
                                               "defect_reason"]
    rows = key.fetchall()
    assert {r[0] for r in rows} == SOURCES                          # every source has planted defects
    assert {r[4] for r in rows} == DIMENSIONS
    assert all(r[5] for r in rows)                                  # every defect says why


def test_one_defect_per_record(built):
    # a record carries at most one planted defect, so "which check caught it" is never ambiguous
    con = duckdb.connect()
    doubles = con.execute(f"""
        SELECT source, record_id, COUNT(*) FROM read_csv('{(built.raw / '_planted_defects.csv').as_posix()}',
                                                         all_varchar = true)
        WHERE record_id IS NOT NULL AND defect_type NOT IN ('late_file', 'missing_file')
        GROUP BY source, record_id HAVING COUNT(*) > 1""").fetchall()
    assert doubles == []


def test_carrier_outage_in_may(built):
    files = {p.stem for p in (built.raw / "carrier_tracking").glob("*.csv")}
    assert {"2026-05-12", "2026-05-13", "2026-05-14"}.isdisjoint(files)   # three days with no carrier file
    assert {"2026-05-11", "2026-05-15"} <= files                          # the feed before and after is fine
    assert len(files) == 184 - 3


def test_brno_feed_stops_in_august(built):
    con = duckdb.connect()
    brno_events = f"""
        SELECT e.file_date, CAST(e.event_at AS DATE) AS event_date
        FROM {raw(built, 'carrier_tracking')} e
        JOIN (SELECT DISTINCT shipment_id, UPPER(TRIM(dc_code)) AS dc_code FROM {raw(built, 'wms_shipments')}) w
          USING (shipment_id)
        WHERE e.carrier_id = 'CR02' AND w.dc_code = 'CZ02'"""
    during = con.execute(f"SELECT COUNT(*) FROM ({brno_events}) "
                         "WHERE file_date BETWEEN DATE '2026-08-06' AND DATE '2026-08-26'").fetchone()[0]
    assert during == 0          # Moravia Express sent nothing for Brno shipments for three weeks
    backfill = con.execute(f"SELECT COUNT(*), MIN(event_date) FROM ({brno_events}) "
                           "WHERE file_date = DATE '2026-08-27' AND event_date < file_date").fetchone()
    assert backfill[0] > 100                      # ... then the backlog arrived in one file on 08-27
    assert backfill[1] == date(2026, 8, 6)        # going back to the first silent day
    before = con.execute(f"SELECT COUNT(*) FROM ({brno_events}) WHERE file_date = DATE '2026-08-05'").fetchone()[0]
    assert before > 0                             # the feed was alive the day before


def test_period_and_volumes(built):
    con = duckdb.connect()
    first, last, orders = con.execute(
        f"SELECT MIN(file_date), MAX(file_date), COUNT(DISTINCT VBELN) FROM {raw(built, 'erp_orders')}").fetchone()
    assert (first, last) == (date(2026, 3, 1), date(2026, 8, 31))
    assert 10_000 < orders < 30_000                               # roughly a hundred orders a day
    assert (last - first) + timedelta(days=1) == timedelta(days=184)
