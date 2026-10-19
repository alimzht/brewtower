"""Delivery KPIs and DQ score maths on a hand-made fixture: run with `pytest`.

tests/fixtures/mini_raw holds six orders placed on Mon 2026-03-02, every file written by hand:

  order     promised  shipped        delivered      what happens                          on time  in full
  50000001  03-03     03-03          03-03 (2 of 2) clean                                 yes      yes
  50000002  03-02     03-02 TransBoh 03-04 (4 of 4) carrier two days late                 no       yes
  50000003  03-02     03-03 (DC late) 03-03 (3 of 3) left the DC a day after the promise   no       yes
  50000004  03-03     03-03          03-03 (12)     line 10 short-picked: 7 of 10 shipped yes      no
  50000005  03-03     03-03          03-03 (5 of 6) one pack lost in transit              yes      no
  50000006  00000000  03-03          03-03          no promised date -> not KPI-eligible   -        -

Feed incidents: the WMS file of 03-03 was extracted at 09:00 the next day (late), the ERP file of 03-04 never came,
and the ERP file of 03-03 is empty (header only). Normal quirks that must NOT be flagged: zero-padded KUNNR,
a WMS dc_code typed " cz01", lowercase statuses from CR04, and customer 100001 renamed in the 03-03 master delta.
"""
import hashlib
import shutil
from datetime import date
from pathlib import Path

import duckdb

from brewtower import pipeline

MINI_RAW = Path(__file__).parent / "fixtures" / "mini_raw"


def test_otd_otif_delay(mini_con):
    otd, otif, delay, eligible = mini_con.execute("""
        SELECT ROUND(100.0 * AVG(is_on_time::INT), 2), ROUND(100.0 * AVG(is_otif::INT), 2), AVG(delay_days), COUNT(*)
        FROM marts.fact_deliveries WHERE kpi_eligible""").fetchone()
    assert eligible == 5        # 50000006 has no promised date
    assert otd == 60.0          # on time: 01, 04, 05 -> 3 / 5
    assert otif == 20.0         # on time AND in full: only 01 -> 1 / 5
    assert delay == 0.6         # delays 0 + 2 + 1 + 0 + 0 = 3 days over 5 orders


def test_per_order_flags(mini_con):
    rows = {r[0]: r[1:] for r in mini_con.execute("""
        SELECT order_id, is_on_time, is_in_full, delay_days, late_cause, kpi_eligible
        FROM marts.fact_deliveries ORDER BY order_id""").fetchall()}
    assert rows[50000001] == (True, True, 0, None, True)
    assert rows[50000002] == (False, True, 2, "carrier_delay", True)        # shipped on time, delivered 2 days late
    assert rows[50000003] == (False, True, 1, "dc_dispatch_delay", True)    # left the DC after the promised date
    assert rows[50000004] == (True, False, 0, None, True)                   # short pick: 7 of 10
    assert rows[50000005] == (True, False, 0, None, True)                   # delivered 5 of 6 shipped
    assert rows[50000006][4] is False                                       # no promised date: not eligible


def test_delivery_kpis_mart(mini_con):
    # the weekly mart agrees with the fact: week of Mon 2026-03-02, by DC and carrier
    rows = mini_con.execute("""
        SELECT dc_code, carrier_id, shipments, otd_pct, otif_pct, avg_delay_days
        FROM marts.delivery_kpis WHERE week_start = DATE '2026-03-02' ORDER BY ALL""").fetchall()
    assert rows == [
        ("CZ01", "CR01", 2, 100.0, 50.0, 0.0),    # 01 clean, 05 short delivered
        ("CZ01", "CR03", 1, 0.0, 0.0, 2.0),       # 02 carrier late by 2 days
        ("CZ02", "CR01", 1, 0.0, 0.0, 1.0),       # 03 DC late by 1 day
        ("CZ02", "CR04", 1, 100.0, 0.0, 0.0),     # 04 short pick
    ]


def test_only_the_planted_issues(mini_con):
    issues = mini_con.execute(
        "SELECT source, date, check_name, dimension, record_id FROM marts.dq_issues ORDER BY ALL").fetchall()
    assert issues == [
        ("erp_orders", date(2026, 3, 2), "missing_promised_date", "completeness", "0050000006/000010"),
        ("erp_orders", date(2026, 3, 4), "missing_file", "freshness", None),
        ("wms_shipments", date(2026, 3, 3), "late_file", "freshness", None),
    ]                           # padded KUNNR, " cz01", "delivered", the rename: none of them flagged


def test_quirks_standardised(mini_con):
    assert mini_con.execute("SELECT customer_id FROM marts.fact_orders WHERE order_id = 50000001").fetchone()[0] == 100001
    assert mini_con.execute("SELECT dc_code FROM staging.wms_shipments WHERE shipment_id = 'SH0000001'").fetchone()[0] == "CZ01"
    assert mini_con.execute("SELECT customer_name FROM marts.dim_customer WHERE customer_id = 100001").fetchone()[0] \
        == "Pub Novak & Sons"   # latest version of the customer wins


def test_dq_score_maths(mini_con):
    score = {(r[0], r[1]): r[2:] for r in mini_con.execute("""
        SELECT source, date, records, completeness_pct, validity_pct, freshness_pct, dq_score
        FROM marts.dq_score_daily""").fetchall()}
    # ERP 03-02: 7 lines, one without a promised date -> completeness 6/7 = 85.71; overall (85.71 + 100 + 100) / 3
    assert score[("erp_orders", date(2026, 3, 2))] == (7, 85.71, 100.0, 100.0, 95.24)
    # ERP 03-03: empty file arrived on time -> nothing to measure but freshness: 100
    assert score[("erp_orders", date(2026, 3, 3))] == (0, None, None, 100.0, 100.0)
    # ERP 03-04: no file -> freshness 0, completeness/validity NULL, overall = mean of the one measured dimension = 0
    assert score[("erp_orders", date(2026, 3, 4))] == (0, None, None, 0.0, 0.0)
    # WMS 03-03: late file -> all 6 lines fail freshness: (100 + 100 + 0) / 3 = 66.67
    assert score[("wms_shipments", date(2026, 3, 3))] == (6, 100.0, 100.0, 0.0, 66.67)
    # carrier feed: every event on time, and the one open shipment (02) updated daily -> 100 every day
    assert {score[("carrier_tracking", date(2026, 3, d))][-1] for d in (2, 3, 4)} == {100.0}
    # master data 03-02: 2 customers + 6 SKUs + 2 DCs + 3 carriers = 13 clean rows
    assert score[("master_data", date(2026, 3, 2))] == (13, 100.0, 100.0, 100.0, 100.0)


def test_empty_and_invalid_values(tmp_path):
    # empty cells arrive as NULL, which "NOT IN (...)" never matches: they need their own completeness checks.
    # Blank master rows are flagged too, and must not switch the validity checks off ("x NOT IN (..., NULL)" is never true).
    raw = tmp_path / "raw"
    shutil.copytree(MINI_RAW, raw)

    def edit(path, old, new):
        text = path.read_text()
        assert text.count(old) == 1, old                    # the fixture changed: update this test
        path.write_text(text.replace(old, new))

    erp, wms = raw / "erp_orders" / "2026-03-02.csv", raw / "wms_shipments" / "2026-03-03.csv"
    edit(erp, "CL-KEG50,2.000,20260303,CZ01", ",,20260303,")              # 50000001: SKU, qty and DC empty
    edit(erp, "TP-KEG30,4.000,20260302,CZ01", "XX-KEG30,abc,20260302,CZ9")  # 50000002: all three present but invalid
    edit(wms, "CZ02,MG-BTL20,3,", ",,,")                                    # SH0000003: empty
    edit(wms, "CZ01,ZL-KEG30,6,", "CZ9,XX-KEG30,-1,")                       # SH0000005: invalid
    for master, blank in (("products", ",,,,,,,"), ("dcs", ",,,"), ("carriers", ",,")):
        f = raw / "master_data" / master / "2026-03-02.csv"
        assert f.read_text().endswith("\n")
        f.write_text(f.read_text() + blank + "2026-03-03 02:05:00\n")

    pipeline.run(raw, tmp_path / "t.duckdb", tmp_path / "gold")
    con = duckdb.connect(str(tmp_path / "t.duckdb"), read_only=True)
    issues = {}
    for record_id, check, dimension in con.execute(
            "SELECT record_id, check_name, dimension FROM marts.dq_issues WHERE record_id IS NOT NULL").fetchall():
        issues.setdefault(record_id, set()).add((check, dimension))
    blank_keys = con.execute("""SELECT (SELECT COUNT(*) FROM marts.dim_sku WHERE sku IS NULL)
        + (SELECT COUNT(*) FROM marts.dim_dc WHERE dc_code IS NULL)
        + (SELECT COUNT(*) FROM marts.dim_carrier WHERE carrier_id IS NULL)""").fetchone()[0]
    con.close()

    empty = {("missing_sku", "completeness"), ("missing_qty", "completeness"), ("missing_dc_code", "completeness")}
    invalid = {("unknown_sku", "validity"), ("nonpositive_qty", "validity"), ("bad_dc_code", "validity")}
    assert issues["0050000001/000010"] == empty
    assert issues["0050000002/000010"] == invalid
    assert issues["SH0000003/10"] == empty
    assert issues["SH0000005/10"] == invalid
    assert issues["products/(empty)"] == {("missing_sku", "completeness")}
    assert issues["dcs/(empty)"] == {("missing_dc_code", "completeness")}
    assert issues["carriers/(empty)"] == {("missing_carrier_id", "completeness")}
    assert blank_keys == 0                                  # blank master rows do not become dimension members


def test_rerun_is_identical(mini):
    # running again on the same database rebuilds everything: same gold files, byte for byte
    def hashes():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(mini.gold.glob("*.csv"))}
    before = hashes()
    pipeline.run(MINI_RAW, mini.db, mini.gold)
    assert hashes() == before
