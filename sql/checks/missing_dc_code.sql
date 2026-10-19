-- completeness | every order line, pick and customer must name its DC; a DC master row must have a code.
SELECT 'master_data' AS source, file_date, record_id, 'missing_dc_code' AS check_name,
       'completeness' AS dimension, 'customer has no dc_code' AS reason, CAST(NULL AS VARCHAR) AS dc_code
FROM staging.customers
WHERE dc_code IS NULL
UNION ALL
SELECT 'master_data', file_date, record_id, 'missing_dc_code', 'completeness', 'DC has no dc_code', NULL
FROM staging.dcs
WHERE dc_code IS NULL
UNION ALL
SELECT 'erp_orders', file_date, record_id, 'missing_dc_code', 'completeness', 'WERKS is empty', NULL
FROM staging.erp_orders
WHERE dc_code IS NULL
UNION ALL
SELECT 'wms_shipments', file_date, record_id, 'missing_dc_code', 'completeness', 'dc_code is empty', NULL
FROM staging.wms_shipments
WHERE dc_code IS NULL
