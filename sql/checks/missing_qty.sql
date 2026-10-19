-- completeness | an order line or pick with no quantity: in-full cannot be measured.
SELECT 'erp_orders' AS source, file_date, record_id, 'missing_qty' AS check_name,
       'completeness' AS dimension, 'KWMENG is empty' AS reason, dc_code
FROM staging.erp_orders
WHERE qty_raw IS NULL
UNION ALL
SELECT 'wms_shipments', file_date, record_id, 'missing_qty', 'completeness', 'shipped_qty is empty', dc_code
FROM staging.wms_shipments
WHERE qty_raw IS NULL
