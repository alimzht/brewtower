-- SAP sales order lines (one row per VBELN/POSNR), typed and standardised.
-- SAP habits are handled here, not flagged: zero-padded numbers, quantities like "12.000", negatives written "5.000-",
-- and 00000000 as the empty date. The raw strings stay next to the typed values, so the checks can tell
-- "missing" (empty) from "present but not a valid value".
SELECT
    file_date,
    VBELN || '/' || POSNR                                   AS record_id,
    CAST(VBELN AS BIGINT)                                   AS order_id,        -- 0050000123 -> 50000123
    CAST(POSNR AS INTEGER)                                  AS order_line,      -- 000010 -> 10
    TRY_STRPTIME(ERDAT, '%Y%m%d')::DATE                     AS order_date,
    NULLIF(TRIM(KUNNR), '')                                 AS customer_raw,
    TRY_CAST(KUNNR AS BIGINT)                               AS customer_id,     -- 0000100123 -> 100123
    UPPER(TRIM(MATNR))                                      AS sku,
    TRY_CAST(TRY_CAST(CASE WHEN KWMENG LIKE '%-' THEN '-' || RTRIM(KWMENG, '-') ELSE KWMENG END
                      AS DECIMAL(12, 3)) AS INTEGER)        AS ordered_qty,     -- "5.000-" -> -5
    NULLIF(TRIM(VDATU), '')                                 AS promised_raw,
    CASE WHEN VDATU <> '00000000' THEN TRY_STRPTIME(VDATU, '%Y%m%d')::DATE END
                                                            AS promised_date,   -- NULL if empty or not a real date
    UPPER(TRIM(WERKS))                                      AS dc_code,
    CAST(extracted_at AS TIMESTAMP)                         AS extracted_at
FROM raw.erp_orders
