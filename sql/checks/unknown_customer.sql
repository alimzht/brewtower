-- validity | a customer number that is present but not in the customer master (an empty one is missing_customer_id).
SELECT 'erp_orders' AS source, file_date, record_id, 'unknown_customer' AS check_name,
       'validity' AS dimension, 'KUNNR ' || customer_raw || ' not in customer master' AS reason, dc_code
FROM staging.erp_orders
WHERE customer_raw IS NOT NULL
  AND (customer_id IS NULL OR customer_id NOT IN (SELECT customer_id FROM staging.customers))
