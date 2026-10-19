-- completeness | an order line or pick with no SKU cannot be priced, picked or reported; a product master row
-- with no SKU cannot be joined at all.
SELECT 'erp_orders' AS source, file_date, record_id, 'missing_sku' AS check_name,
       'completeness' AS dimension, 'MATNR is empty' AS reason, dc_code
FROM staging.erp_orders
WHERE sku IS NULL
UNION ALL
SELECT 'wms_shipments', file_date, record_id, 'missing_sku', 'completeness', 'sku is empty', dc_code
FROM staging.wms_shipments
WHERE sku IS NULL
UNION ALL
SELECT 'master_data', file_date, record_id, 'missing_sku', 'completeness', 'product has no sku', NULL
FROM staging.products
WHERE sku IS NULL
