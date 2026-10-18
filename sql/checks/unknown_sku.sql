-- validity | every SKU on an order or a pick must exist in the product master.
SELECT 'erp_orders' AS source, file_date, record_id, 'unknown_sku' AS check_name,
       'validity' AS dimension, 'MATNR ' || sku || ' not in product master' AS reason, dc_code
FROM staging.erp_orders
WHERE sku NOT IN (SELECT sku FROM staging.products)
UNION ALL
SELECT 'wms_shipments', file_date, record_id, 'unknown_sku',
       'validity', 'sku ' || sku || ' not in product master', dc_code
FROM staging.wms_shipments
WHERE sku NOT IN (SELECT sku FROM staging.products)
