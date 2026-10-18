-- Carrier status events. One carrier sends lowercase statuses ("delivered"): standardised, not flagged.
SELECT
    file_date,
    event_id                                                AS record_id,
    event_id,
    shipment_id,
    UPPER(TRIM(carrier_id))                                 AS carrier_id,
    UPPER(TRIM(status))                                     AS status,
    CAST(event_at AS TIMESTAMP)                             AS event_at,
    TRY_CAST(delivered_qty AS INTEGER)                      AS delivered_qty,
    CAST(extracted_at AS TIMESTAMP)                         AS extracted_at
FROM raw.carrier_tracking
