-- completeness | a shipped line with no carrier cannot be matched to tracking or charged to a carrier; a carrier
-- master row with no code cannot be joined at all.
SELECT 'wms_shipments' AS source, file_date, record_id, 'missing_carrier_id' AS check_name,
       'completeness' AS dimension, 'carrier_id is empty' AS reason, dc_code
FROM staging.wms_shipments
WHERE carrier_id IS NULL
UNION ALL
SELECT 'master_data', file_date, record_id, 'missing_carrier_id', 'completeness', 'carrier has no carrier_id', NULL
FROM staging.carriers
WHERE carrier_id IS NULL
