-- validity | customer_type drives lead times and reporting: it must be one of the three known types.
SELECT 'master_data' AS source, file_date, record_id, 'invalid_customer_type' AS check_name,
       'validity' AS dimension, 'customer_type ' || COALESCE(customer_type, 'NULL') || ' is not bar, retailer or wholesaler' AS reason,
       dc_code
FROM staging.customers
WHERE customer_type IS NULL OR customer_type NOT IN ('bar', 'retailer', 'wholesaler')
