-- validity | delivery cannot be promised for a day before the order was placed.
SELECT 'erp_orders' AS source, file_date, record_id, 'promised_before_ordered' AS check_name,
       'validity' AS dimension, 'VDATU ' || promised_date || ' is before ERDAT ' || order_date AS reason, dc_code
FROM staging.erp_orders
WHERE promised_date < order_date
