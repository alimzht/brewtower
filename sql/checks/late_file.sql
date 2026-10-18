-- freshness | each day's file must be extracted by 06:00 the next morning (the SLA). One row per late file; the DQ
-- score then counts every record in that file as not fresh. record_id is empty, or the entity for master data.
-- A header-only file carries no extracted_at, so it can only be checked for being there (missing_file).
WITH extracts AS (
    SELECT 'erp_orders' AS source, CAST(NULL AS VARCHAR) AS entity, file_date, MAX(extracted_at) AS extracted_at
    FROM staging.erp_orders GROUP BY file_date
    UNION ALL
    SELECT 'wms_shipments', NULL, file_date, MAX(extracted_at) FROM staging.wms_shipments GROUP BY file_date
    UNION ALL
    SELECT 'carrier_tracking', NULL, file_date, MAX(extracted_at) FROM staging.carrier_events GROUP BY file_date
    UNION ALL
    SELECT 'master_data', 'customers', file_date, MAX(extracted_at) FROM staging.customers GROUP BY file_date
    UNION ALL
    SELECT 'master_data', 'products', file_date, MAX(extracted_at) FROM staging.products GROUP BY file_date
    UNION ALL
    SELECT 'master_data', 'dcs', file_date, MAX(extracted_at) FROM staging.dcs GROUP BY file_date
    UNION ALL
    SELECT 'master_data', 'carriers', file_date, MAX(extracted_at) FROM staging.carriers GROUP BY file_date
)
SELECT source, file_date, entity AS record_id, 'late_file' AS check_name, 'freshness' AS dimension,
       'extracted ' || strftime(extracted_at, '%Y-%m-%d %H:%M') || ', SLA is 06:00 the next day' AS reason,
       CAST(NULL AS VARCHAR) AS dc_code
FROM extracts
WHERE extracted_at > file_date + INTERVAL 1 DAY + INTERVAL 6 HOUR
