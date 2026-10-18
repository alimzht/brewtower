-- Carriers.
SELECT
    file_date,
    'carriers/' || UPPER(TRIM(carrier_id))                  AS record_id,
    UPPER(TRIM(carrier_id))                                 AS carrier_id,
    carrier_name,
    CAST(extracted_at AS TIMESTAMP)                         AS extracted_at
FROM raw.master_carriers
