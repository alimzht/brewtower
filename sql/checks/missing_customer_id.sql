-- completeness | an order line with no customer (KUNNR empty) cannot be delivered or billed.
SELECT 'erp_orders' AS source, file_date, record_id, 'missing_customer_id' AS check_name,
       'completeness' AS dimension, 'KUNNR is empty' AS reason, dc_code
FROM staging.erp_orders
WHERE customer_raw IS NULL
