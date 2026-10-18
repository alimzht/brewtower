-- validity | a master-data key may appear only once per file. One row per duplicated key; "conflicting" means the
-- copies disagree, so it is unclear which one is right. (The same key in a later file is an update, not a duplicate.)
SELECT 'master_data' AS source, file_date, record_id, 'duplicate_key' AS check_name, 'validity' AS dimension,
       'customer_id appears ' || COUNT(*) || ' times in one file'
           || CASE WHEN COUNT(DISTINCT (customer_name, customer_type, dc_code)) > 1 THEN ', conflicting' ELSE ', identical' END
           AS reason,
       CAST(NULL AS VARCHAR) AS dc_code
FROM staging.customers
GROUP BY file_date, record_id
HAVING COUNT(*) > 1
UNION ALL
SELECT 'master_data', file_date, record_id, 'duplicate_key', 'validity',
       'sku appears ' || COUNT(*) || ' times in one file'
           || CASE WHEN COUNT(DISTINCT (sku_name, pack, liters_per_pack)) > 1 THEN ', conflicting' ELSE ', identical' END,
       NULL
FROM staging.products
GROUP BY file_date, record_id
HAVING COUNT(*) > 1
UNION ALL
SELECT 'master_data', file_date, record_id, 'duplicate_key', 'validity', 'dc_code appears ' || COUNT(*) || ' times in one file', NULL
FROM staging.dcs
GROUP BY file_date, record_id
HAVING COUNT(*) > 1
UNION ALL
SELECT 'master_data', file_date, record_id, 'duplicate_key', 'validity', 'carrier_id appears ' || COUNT(*) || ' times in one file', NULL
FROM staging.carriers
GROUP BY file_date, record_id
HAVING COUNT(*) > 1
