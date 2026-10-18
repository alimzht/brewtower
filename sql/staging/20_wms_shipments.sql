-- Warehouse picks: one row per shipment line. DC codes typed by hand (" cz01") are trimmed and upper-cased.
SELECT
    file_date,
    shipment_id || '/' || order_line                        AS record_id,
    shipment_id,
    CAST(order_id AS BIGINT)                                AS order_id,
    CAST(order_line AS INTEGER)                             AS order_line,
    UPPER(TRIM(dc_code))                                    AS dc_code,
    UPPER(TRIM(sku))                                        AS sku,
    TRY_CAST(shipped_qty AS INTEGER)                        AS shipped_qty,
    NULLIF(UPPER(TRIM(carrier_id)), '')                     AS carrier_id,
    CAST(shipped_at AS TIMESTAMP)                           AS shipped_at,
    CAST(extracted_at AS TIMESTAMP)                         AS extracted_at
FROM raw.wms_shipments
