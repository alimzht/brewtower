-- Distribution centres.
SELECT
    file_date,
    'dcs/' || COALESCE(NULLIF(UPPER(TRIM(dc_code)), ''), '(empty)')
                                                            AS record_id,
    NULLIF(UPPER(TRIM(dc_code)), '')                        AS dc_code,
    dc_name,
    city,
    CAST(extracted_at AS TIMESTAMP)                         AS extracted_at
FROM raw.master_dcs
