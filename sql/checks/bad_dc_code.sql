-- validity | DC codes must exist in the DC master (after trimming and upper-casing in staging).
SELECT 'erp_orders' AS source, file_date, record_id, 'bad_dc_code' AS check_name,
       'validity' AS dimension, 'WERKS ' || dc_code || ' is not a known DC' AS reason, dc_code
FROM staging.erp_orders
WHERE dc_code NOT IN (SELECT dc_code FROM staging.dcs)
UNION ALL
SELECT 'wms_shipments', file_date, record_id, 'bad_dc_code',
       'validity', 'dc_code ' || dc_code || ' is not a known DC', dc_code
FROM staging.wms_shipments
WHERE dc_code NOT IN (SELECT dc_code FROM staging.dcs)
UNION ALL
SELECT 'master_data', file_date, record_id, 'bad_dc_code',
       'validity', 'customer dc_code ' || dc_code || ' is not a known DC', dc_code
FROM staging.customers
WHERE dc_code NOT IN (SELECT dc_code FROM staging.dcs)
