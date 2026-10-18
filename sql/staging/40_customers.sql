-- Every customer row ever received (full load on day 1, then deltas). Versions are resolved later, in dim_customer.
SELECT
    file_date,
    'customers/' || CAST(CAST(customer_id AS BIGINT) AS VARCHAR) AS record_id,
    CAST(customer_id AS BIGINT)                             AS customer_id,
    TRIM(customer_name)                                     AS customer_name,
    LOWER(TRIM(customer_type))                              AS customer_type,
    NULLIF(UPPER(TRIM(dc_code)), '')                        AS dc_code,
    TRIM(city)                                              AS city,
    CAST(valid_from AS DATE)                                AS valid_from,
    CAST(extracted_at AS TIMESTAMP)                         AS extracted_at
FROM raw.master_customers
