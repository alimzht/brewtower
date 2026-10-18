-- validity | a requested delivery date that is present but is not a calendar date (e.g. 20260231).
SELECT 'erp_orders' AS source, file_date, record_id, 'invalid_date' AS check_name,
       'validity' AS dimension, 'VDATU ' || promised_raw || ' is not a calendar date' AS reason, dc_code
FROM staging.erp_orders
WHERE promised_raw <> '00000000' AND promised_date IS NULL
