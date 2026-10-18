-- completeness | a shipped line with no carrier cannot be matched to tracking or charged to a carrier.
SELECT 'wms_shipments' AS source, file_date, record_id, 'missing_carrier_id' AS check_name,
       'completeness' AS dimension, 'carrier_id is empty' AS reason, dc_code
FROM staging.wms_shipments
WHERE carrier_id IS NULL
