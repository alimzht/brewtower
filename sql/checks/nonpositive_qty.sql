-- validity | quantities ordered or shipped must be positive (SAP's "5.000-" is already -5 after staging).
SELECT 'erp_orders' AS source, file_date, record_id, 'nonpositive_qty' AS check_name,
       'validity' AS dimension, 'KWMENG is ' || ordered_qty AS reason, dc_code
FROM staging.erp_orders
WHERE ordered_qty <= 0
UNION ALL
SELECT 'wms_shipments', file_date, record_id, 'nonpositive_qty',
       'validity', 'shipped_qty is ' || shipped_qty, dc_code
FROM staging.wms_shipments
WHERE shipped_qty <= 0
