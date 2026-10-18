"""Tests for the pipeline on the full synthetic dataset: run with `pytest`.

The answer key (data/raw/_planted_defects.csv) says which defects were planted. The pipeline must catch every one
of them with the right check and dimension, flag nothing else (except stale open shipments, which it derives),
leave normal source quirks alone, and never drop a record.
"""
import hashlib

import pytest

from brewtower import pipeline

DEFECT_TYPES = [
    "bad_dc_code", "delivered_before_shipped", "duplicate_key", "event_after_extraction", "invalid_customer_type",
    "invalid_date", "late_arriving_record", "late_file", "missing_carrier_id", "missing_customer_id",
    "missing_dc_code", "missing_delivered_qty", "missing_file", "missing_promised_date", "nonpositive_qty",
    "promised_before_ordered", "unknown_customer", "unknown_sku"]

MATCH = """i.source = k.source AND i.date = k.date AND i.check_name = k.defect_type AND i.dimension = k.dimension
           AND i.record_id IS NOT DISTINCT FROM k.record_id"""


def test_every_defect_type_is_tested(con):
    assert sorted(r[0] for r in con.execute("SELECT DISTINCT defect_type FROM planted").fetchall()) == DEFECT_TYPES


@pytest.mark.parametrize("defect_type", DEFECT_TYPES)
def test_planted_defects_caught(con, defect_type):
    planted, missed = con.execute(f"""
        SELECT COUNT(*), COUNT(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM marts.dq_issues i WHERE {MATCH}))
        FROM planted k WHERE k.defect_type = ?""", [defect_type]).fetchone()
    assert planted > 0
    assert missed == 0          # same source, day, record, check name and dimension


def test_no_false_positives(con):
    extras = con.execute(f"""
        SELECT check_name, COUNT(*) FROM marts.dq_issues i
        WHERE check_name <> 'stale_open_shipment' AND NOT EXISTS (SELECT 1 FROM planted k WHERE {MATCH})
        GROUP BY check_name""").fetchall()
    assert extras == []


def test_stale_shipments_only_during_outages(con):
    # stale_open_shipment is derived, not planted: it must appear only while a carrier feed is silent
    outside = con.execute("""
        SELECT COUNT(*) FROM marts.dq_issues WHERE check_name = 'stale_open_shipment'
          AND date NOT BETWEEN DATE '2026-05-12' AND DATE '2026-05-16'
          AND date NOT BETWEEN DATE '2026-08-06' AND DATE '2026-08-28'""").fetchone()[0]
    assert outside == 0
    brno = con.execute("""
        SELECT COUNT(*) FILTER (WHERE dc_code = 'CZ02') * 1.0 / COUNT(*) FROM marts.dq_issues
        WHERE check_name = 'stale_open_shipment' AND date BETWEEN DATE '2026-08-06' AND DATE '2026-08-28'""").fetchone()[0]
    assert brno > 0.99          # in August it is the Brno shipments that go stale


def test_zero_padded_customer_numbers_match_master(con):
    # SAP pads KUNNR to 10 digits (0000100123), the master does not (100123): standardised, not "unknown"
    padded, flagged = con.execute("""
        SELECT COUNT(*), COUNT(i.record_id)
        FROM staging.erp_orders o
        JOIN raw.erp_orders r ON r.VBELN || '/' || r.POSNR = o.record_id
        LEFT JOIN marts.dq_issues i ON i.record_id = o.record_id AND i.check_name = 'unknown_customer'
        WHERE r.KUNNR LIKE '0000%' AND o.customer_id IN (SELECT customer_id FROM staging.customers)""").fetchone()
    assert padded > 40_000
    assert flagged == 0


def test_messy_dc_codes_not_flagged(con):
    # the WMS sometimes has " cz01": trimmed and upper-cased in staging, not a bad DC code
    messy, flagged = con.execute("""
        SELECT COUNT(*), COUNT(i.record_id)
        FROM raw.wms_shipments r
        LEFT JOIN marts.dq_issues i ON i.record_id = r.shipment_id || '/' || r.order_line AND i.check_name = 'bad_dc_code'
        WHERE r.dc_code <> UPPER(TRIM(r.dc_code)) AND UPPER(TRIM(r.dc_code)) IN (SELECT dc_code FROM staging.dcs)""").fetchone()
    assert messy > 100
    assert flagged == 0


def test_lowercase_statuses_standardised(con):
    # Silesia Logistics (CR04) sends "delivered": counted as DELIVERED, so its shipments get delivery KPIs
    assert con.execute("SELECT COUNT(*) FROM raw.carrier_tracking WHERE status = 'delivered'").fetchone()[0] > 1000
    assert {r[0] for r in con.execute("SELECT DISTINCT status FROM staging.carrier_events").fetchall()} == {
        "PICKED_UP", "IN_TRANSIT", "DELIVERED"}
    delivered = con.execute(
        "SELECT COUNT(*) FROM marts.fact_deliveries WHERE carrier_id = 'CR04' AND is_delivered").fetchone()[0]
    assert delivered > 1000


def test_master_updates_are_not_duplicates(con):
    # the same customer in a later file is an update (renamed "& Sons"), not a duplicate; the dim keeps the latest
    renamed = con.execute("""
        SELECT customer_id FROM staging.customers WHERE customer_name LIKE '% & Sons'""").fetchall()
    assert len(renamed) == 8
    ids = [r[0] for r in renamed]
    flagged = con.execute(f"""
        SELECT COUNT(*) FROM marts.dq_issues i
        WHERE i.check_name = 'duplicate_key' AND i.record_id IN (SELECT 'customers/' || x FROM UNNEST(?) t(x))
          AND NOT EXISTS (SELECT 1 FROM planted k WHERE {MATCH})""", [ids]).fetchone()[0]
    assert flagged == 0
    in_dim = con.execute("""
        SELECT COUNT(*) FROM marts.dim_customer WHERE customer_id IN (SELECT UNNEST(?)) AND customer_name LIKE '% & Sons'""",
                         [ids]).fetchone()[0]
    assert in_dim == 8


def test_nothing_dropped(con):
    raw_lines = con.execute("SELECT COUNT(*) FROM raw.erp_orders").fetchone()[0]
    assert con.execute("SELECT COUNT(*) FROM marts.fact_orders").fetchone()[0] == raw_lines   # one row per SAP line
    orders = con.execute("SELECT COUNT(DISTINCT VBELN) FROM raw.erp_orders").fetchone()[0]
    assert con.execute("SELECT COUNT(*) FROM marts.fact_deliveries").fetchone()[0] == orders  # one row per order
    # every ERP line with an issue is still in the fact, marked has_dq_issue
    unflagged = con.execute("""
        SELECT COUNT(*) FROM marts.dq_issues i
        JOIN marts.fact_orders f ON f.order_line_key = i.record_id
        WHERE i.source = 'erp_orders' AND NOT f.has_dq_issue""").fetchone()[0]
    assert unflagged == 0
    issue_lines = con.execute("SELECT COUNT(DISTINCT record_id) FROM marts.dq_issues WHERE source = 'erp_orders' "
                              "AND record_id IS NOT NULL").fetchone()[0]
    assert con.execute("SELECT COUNT(*) FROM marts.fact_orders WHERE has_dq_issue").fetchone()[0] == issue_lines


def test_dq_score_is_mean_of_dimensions(con):
    # overall = mean of the dimensions measured that day (rounding to 2 decimals allows a 0.01 gap)
    off = con.execute("""
        SELECT COUNT(*) FROM marts.dq_score_daily
        WHERE ABS(dq_score - (COALESCE(completeness_pct, 0) + COALESCE(validity_pct, 0) + freshness_pct)
                             / (1 + (completeness_pct IS NOT NULL)::INT + (validity_pct IS NOT NULL)::INT)) > 0.01""").fetchone()[0]
    assert off == 0
    assert con.execute("SELECT COUNT(*) FROM marts.dq_score_daily").fetchone()[0] == 4 * 184   # every source, every day


def test_transbohemia_is_the_late_carrier(con):
    # the generator makes CR03 late far more often; the KPIs must show it
    otd = dict(con.execute("""
        SELECT carrier_id, AVG(is_on_time::INT) FROM marts.fact_deliveries
        WHERE kpi_eligible GROUP BY carrier_id""").fetchall())
    assert min(otd, key=otd.get) == "CR03"


def test_rerun_is_identical(built):
    # each run drops and rebuilds every schema in the same database: the gold CSVs come out byte-identical
    def hashes():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(built.gold.glob("*.csv"))}
    before = hashes()
    pipeline.run(built.raw, built.db, built.gold)
    assert hashes() == before
    assert len(before) == len(pipeline.GOLD_TABLES)
