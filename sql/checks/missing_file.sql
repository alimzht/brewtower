-- freshness | every feed must deliver a file for every day of the period, even an empty one (header only).
-- raw.files lists the files that arrived, including empty ones; a day with no file is a feed outage.
WITH days AS (
    SELECT CAST(UNNEST(generate_series(MIN(file_date), MAX(file_date), INTERVAL 1 DAY)) AS DATE) AS file_date
    FROM raw.files
),
feeds AS (
    SELECT DISTINCT source, entity FROM raw.files
)
SELECT f.source, d.file_date, f.entity AS record_id, 'missing_file' AS check_name, 'freshness' AS dimension,
       'no file received for this day' AS reason, CAST(NULL AS VARCHAR) AS dc_code
FROM feeds f
CROSS JOIN days d
WHERE NOT EXISTS (
    SELECT 1 FROM raw.files r
    WHERE r.source = f.source AND r.entity IS NOT DISTINCT FROM f.entity AND r.file_date = d.file_date
)
