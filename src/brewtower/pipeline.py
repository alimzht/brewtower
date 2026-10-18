"""Run the pipeline: raw daily files -> staging -> checks -> marts in DuckDB, then the gold CSVs Power BI imports.

    python -m brewtower.pipeline

Python only orchestrates. Every transformation is a SQL file under sql/, one SELECT per file, and the file name is
the table name: sql/staging/10_erp_orders.sql -> staging.erp_orders, sql/checks/late_file.sql -> checks.late_file.
Files run in name order. Each run drops and rebuilds every schema, so re-running gives identical output.

  raw       the CSVs as received (all text) + raw.files, the list of files that arrived (empty ones included)
  staging   typed and standardised; SAP formats decoded; nothing removed
  checks    one table per check: the records that fail it, with source, check_name, dimension and reason
  marts     star schema + dq_issues + dq_score_daily + delivery_kpis -> data/gold/*.csv
"""
import re
import time
from pathlib import Path

import duckdb

from brewtower.paths import GOLD, RAW, ROOT, SQL

FEEDS = {  # raw table -> (source, master-data entity, folder under data/raw)
    "erp_orders": ("erp_orders", None, "erp_orders"),
    "wms_shipments": ("wms_shipments", None, "wms_shipments"),
    "carrier_tracking": ("carrier_tracking", None, "carrier_tracking"),
    "master_customers": ("master_data", "customers", "master_data/customers"),
    "master_products": ("master_data", "products", "master_data/products"),
    "master_dcs": ("master_data", "dcs", "master_data/dcs"),
    "master_carriers": ("master_data", "carriers", "master_data/carriers"),
}
GOLD_TABLES = ["fact_orders", "fact_deliveries", "dim_customer", "dim_sku", "dim_dc", "dim_carrier", "dim_date",
               "dq_issues", "dq_score_daily", "delivery_kpis"]
FILE_DATE = r"CAST(regexp_extract({col}, '(\d{{4}}-\d{{2}}-\d{{2}})\.csv$', 1) AS DATE)"


def load_raw(con, raw_dir: Path):
    """Load each feed's daily CSVs as text. Files starting with '_' (the answer key) are not data: the glob skips them."""
    listed = []
    for table, (source, entity, folder) in FEEDS.items():
        pattern = (raw_dir / folder / "[0-9]*.csv").as_posix()
        con.execute(f"""
            CREATE TABLE raw.{table} AS
            SELECT * EXCLUDE (filename), {FILE_DATE.format(col='filename')} AS file_date
            FROM read_csv('{pattern}', all_varchar = true, header = true, filename = true, union_by_name = true)""")
        entity_sql = f"'{entity}'" if entity else "CAST(NULL AS VARCHAR)"
        listed.append(f"SELECT '{source}' AS source, {entity_sql} AS entity, {FILE_DATE.format(col='file')} AS file_date "
                      f"FROM glob('{pattern}')")
    con.execute("CREATE TABLE raw.files AS " + " UNION ALL ".join(listed))


def run_layer(con, layer: str):
    for path in sorted((SQL / layer).glob("*.sql")):
        name = re.sub(r"^\d+_", "", path.stem)
        con.execute(f"CREATE TABLE {layer}.{name} AS\n{path.read_text(encoding='utf-8').strip().rstrip(';')}")


def union_checks(con):
    """checks.all_issues = every check table stacked; marts.dq_issues reads it."""
    checks = [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'checks' ORDER BY table_name").fetchall()]
    con.execute("CREATE TABLE checks.all_issues AS " + " UNION ALL ".join(
        f"SELECT source, file_date, record_id, check_name, dimension, reason, dc_code FROM checks.{c}" for c in checks))


def export_gold(con, gold_dir: Path):
    gold_dir.mkdir(parents=True, exist_ok=True)
    for table in GOLD_TABLES:   # ORDER BY ALL: same rows in the same order on every run
        target = (gold_dir / f"{table}.csv").as_posix()
        con.execute(f"COPY (SELECT * FROM marts.{table} ORDER BY ALL) TO '{target}' (HEADER, DELIMITER ',')")


def catch_rate(con, raw_dir: Path):
    """Compare dq_issues with the generator's answer key: (planted, caught, extra issues per check)."""
    key = raw_dir / "_planted_defects.csv"
    if not key.exists():
        return None
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE planted AS
        SELECT source, CAST(file_date AS DATE) AS date, record_id, defect_type AS check_name
        FROM read_csv('{key.as_posix()}', all_varchar = true, header = true)""")
    matched = """k.source = i.source AND k.date = i.date AND k.check_name = i.check_name
                 AND k.record_id IS NOT DISTINCT FROM i.record_id"""
    planted, caught = con.execute(f"""
        SELECT COUNT(*), COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM marts.dq_issues i WHERE {matched}))
        FROM planted k""").fetchone()
    extras = con.execute(f"""
        SELECT check_name, COUNT(*) FROM marts.dq_issues i
        WHERE NOT EXISTS (SELECT 1 FROM planted k WHERE {matched})
        GROUP BY check_name ORDER BY check_name""").fetchall()
    return planted, caught, dict(extras)


def run(raw_dir: Path = RAW, db_path: Path = ROOT / "data" / "brewtower.duckdb", gold_dir: Path = GOLD) -> dict:
    started = time.perf_counter()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        for schema in ("marts", "checks", "staging", "raw"):
            con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        for schema in ("raw", "staging", "checks", "marts"):
            con.execute(f"CREATE SCHEMA {schema}")

        load_raw(con, raw_dir)
        run_layer(con, "staging")
        run_layer(con, "checks")
        union_checks(con)
        run_layer(con, "marts")
        export_gold(con, gold_dir)

        tables = [f"{s}.{t}" for s, t in con.execute(
            "SELECT schema_name, table_name FROM duckdb_tables() ORDER BY schema_name, table_name").fetchall()]
        rows = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
        issues = dict(con.execute(
            "SELECT check_name, COUNT(*) FROM marts.dq_issues GROUP BY check_name ORDER BY check_name").fetchall())
        result = {"rows": rows, "issues": issues, "catch": catch_rate(con, raw_dir),
                  "seconds": round(time.perf_counter() - started, 1)}
    finally:
        con.close()
    return result


def main():
    result = run()
    for layer in ("raw", "staging", "marts"):
        tables = {k: v for k, v in result["rows"].items() if k.startswith(layer + ".")}
        print(f"{layer:8} {len(tables)} tables, {sum(tables.values()):,} rows")
    print("\nissues per check")
    for check, n in result["issues"].items():
        print(f"  {check:26} {n:7,}")
    if result["catch"]:
        planted, caught, extras = result["catch"]
        print(f"\nplanted defects caught: {caught:,} of {planted:,} ({caught / planted:.1%})")
        print("issues not in the answer key: " + (", ".join(f"{c} {n:,}" for c, n in extras.items()) or "none"))
    print(f"\ngold CSVs in {GOLD} ({result['seconds']} s)")


if __name__ == "__main__":
    main()
