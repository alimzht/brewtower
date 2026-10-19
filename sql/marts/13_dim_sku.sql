-- One row per SKU (latest version; duplicates resolved deterministically), plus an UNKNOWN member.
WITH ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY sku ORDER BY file_date DESC, sku_name, pack) AS version_rank
    FROM staging.products
    WHERE sku IS NOT NULL               -- a blank master row is flagged (missing_sku), not a product
)
SELECT sku, sku_name, brand, brewery, pack, liters_per_pack, launched_on
FROM ranked
WHERE version_rank = 1
UNION ALL
SELECT 'UNKNOWN', 'Unknown SKU', 'Unknown', 'Unknown', 'UNKNOWN', NULL, NULL
