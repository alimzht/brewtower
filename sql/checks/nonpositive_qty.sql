-- validity | quantities ordered or shipped must be positive numbers (SAP's "5.000-" is already -5 after staging).
-- A quantity that is there but is not a number fails too; an empty one is missing_qty.
SELECT 'erp_orders' AS source, file_date, record_id, 'nonpositive_qty' AS check_name,
       'validity' AS dimension, 'KWMENG is ' || COALESCE(CAST(ordered_qty AS VARCHAR), qty_raw || ', not a number') AS reason,
       dc_code
FROM staging.erp_orders
WHERE ordered_qty <= 0 OR (ordered_qty IS NULL AND qty_raw IS NOT NULL)
UNION ALL
SELECT 'wms_shipments', file_date, record_id, 'nonpositive_qty',
       'validity', 'shipped_qty is ' || COALESCE(CAST(shipped_qty AS VARCHAR), qty_raw || ', not a number'), dc_code
FROM staging.wms_shipments
WHERE shipped_qty <= 0 OR (shipped_qty IS NULL AND qty_raw IS NOT NULL)
