-- One row per SKU (latest version; duplicates resolved deterministically), plus an UNKNOWN member.
WITH ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY sku ORDER BY file_date DESC, sku_name, pack) AS version_rank
    FROM staging.products
)
SELECT sku, sku_name, brand, brewery, pack, liters_per_pack, launched_on
FROM ranked
WHERE version_rank = 1
UNION ALL
SELECT 'UNKNOWN', 'Unknown SKU', 'Unknown', 'Unknown', 'UNKNOWN', NULL, NULL
