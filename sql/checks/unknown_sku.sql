-- validity | every SKU on an order or a pick must exist in the product master (an empty one is missing_sku).
-- IS NOT NULL in the subquery: one blank master row would otherwise make NOT IN match nothing.
SELECT 'erp_orders' AS source, file_date, record_id, 'unknown_sku' AS check_name,
       'validity' AS dimension, 'MATNR ' || sku || ' not in product master' AS reason, dc_code
FROM staging.erp_orders
WHERE sku NOT IN (SELECT sku FROM staging.products WHERE sku IS NOT NULL)
UNION ALL
SELECT 'wms_shipments', file_date, record_id, 'unknown_sku',
       'validity', 'sku ' || sku || ' not in product master', dc_code
FROM staging.wms_shipments
WHERE sku NOT IN (SELECT sku FROM staging.products WHERE sku IS NOT NULL)
