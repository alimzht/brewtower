-- completeness | no requested delivery date (empty, or SAP's null date 00000000): on-time cannot be measured.
SELECT 'erp_orders' AS source, file_date, record_id, 'missing_promised_date' AS check_name,
       'completeness' AS dimension, 'VDATU is empty or 00000000' AS reason, dc_code
FROM staging.erp_orders
WHERE promised_raw IS NULL OR promised_raw = '00000000'
