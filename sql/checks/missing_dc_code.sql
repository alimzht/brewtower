-- completeness | every customer must be assigned to the DC that serves it.
SELECT 'master_data' AS source, file_date, record_id, 'missing_dc_code' AS check_name,
       'completeness' AS dimension, 'customer has no dc_code' AS reason, CAST(NULL AS VARCHAR) AS dc_code
FROM staging.customers
WHERE dc_code IS NULL
