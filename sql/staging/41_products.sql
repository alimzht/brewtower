-- Every product (SKU) row received.
SELECT
    file_date,
    'products/' || COALESCE(NULLIF(UPPER(TRIM(sku)), ''), '(empty)')
                                                            AS record_id,
    NULLIF(UPPER(TRIM(sku)), '')                            AS sku,
    sku_name,
    brand,
    brewery,
    UPPER(TRIM(pack))                                       AS pack,
    CAST(liters_per_pack AS DOUBLE)                         AS liters_per_pack,
    CAST(launched_on AS DATE)                               AS launched_on,
    CAST(extracted_at AS TIMESTAMP)                         AS extracted_at
FROM raw.master_products
