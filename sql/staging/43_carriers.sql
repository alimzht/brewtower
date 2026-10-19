-- Carriers.
SELECT
    file_date,
    'carriers/' || COALESCE(NULLIF(UPPER(TRIM(carrier_id)), ''), '(empty)')
                                                            AS record_id,
    NULLIF(UPPER(TRIM(carrier_id)), '')                     AS carrier_id,
    carrier_name,
    CAST(extracted_at AS TIMESTAMP)                         AS extracted_at
FROM raw.master_carriers
