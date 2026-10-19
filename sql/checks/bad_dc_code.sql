-- validity | DC codes must exist in the DC master (after trimming and upper-casing in staging; an empty one is
-- missing_dc_code). IS NOT NULL in the subquery: one blank master row would otherwise make NOT IN match nothing.
SELECT 'erp_orders' AS source, file_date, record_id, 'bad_dc_code' AS check_name,
       'validity' AS dimension, 'WERKS ' || dc_code || ' is not a known DC' AS reason, dc_code
FROM staging.erp_orders
WHERE dc_code NOT IN (SELECT dc_code FROM staging.dcs WHERE dc_code IS NOT NULL)
UNION ALL
SELECT 'wms_shipments', file_date, record_id, 'bad_dc_code',
       'validity', 'dc_code ' || dc_code || ' is not a known DC', dc_code
FROM staging.wms_shipments
WHERE dc_code NOT IN (SELECT dc_code FROM staging.dcs WHERE dc_code IS NOT NULL)
UNION ALL
SELECT 'master_data', file_date, record_id, 'bad_dc_code',
       'validity', 'customer dc_code ' || dc_code || ' is not a known DC', dc_code
FROM staging.customers
WHERE dc_code NOT IN (SELECT dc_code FROM staging.dcs WHERE dc_code IS NOT NULL)
