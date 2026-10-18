-- One row per customer: the latest valid version received (a valid row beats a newer broken one). Duplicates inside
-- one file are resolved deterministically here and reported by the duplicate_key check. Invalid values become
-- 'unknown' / UNKNOWN so the customer still joins. Customer -1 is the UNKNOWN member for unknown or missing KUNNR.
WITH ranked AS (
    SELECT *,
           MIN(file_date) OVER (PARTITION BY customer_id) AS first_seen,
           ROW_NUMBER() OVER (
               PARTITION BY customer_id
               ORDER BY (dc_code IN (SELECT dc_code FROM staging.dcs)
                         AND customer_type IN ('bar', 'retailer', 'wholesaler')) DESC,
                        file_date DESC, dc_code, customer_type, customer_name
           ) AS version_rank
    FROM staging.customers
)
SELECT customer_id,
       customer_name,
       CASE WHEN customer_type IN ('bar', 'retailer', 'wholesaler') THEN customer_type ELSE 'unknown' END AS customer_type,
       CASE WHEN dc_code IN (SELECT dc_code FROM staging.dcs) THEN dc_code ELSE 'UNKNOWN' END AS dc_code,
       city,
       first_seen,
       file_date AS valid_from
FROM ranked
WHERE version_rank = 1
UNION ALL
SELECT -1, 'Unknown customer', 'unknown', 'UNKNOWN', NULL, NULL, NULL
