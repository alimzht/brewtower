-- Data-quality score per source per day, 0-100.
--   completeness_pct / validity_pct / freshness_pct = % of that day's records with no issue in that dimension
--   dq_score = mean of the three (of the ones that exist that day), so "why 87?" is answered by the breakdown.
-- Rules:
--   * a late file (late_file) makes every record in it fail freshness;
--   * a day with no file (missing_file) scores freshness 0; completeness and validity are NULL (nothing to measure),
--     and dq_score is the mean of the dimensions that are not NULL;
--   * carrier_tracking: open shipments that day are in the freshness denominator; stale ones (stale_open_shipment) fail;
--   * a day with a file but no records (header only) scores freshness 100: the file arrived, and nothing else to measure.
WITH record_flags AS (               -- record-level issues: which dimensions each record fails
    SELECT source, date, record_id,
           BOOL_OR(dimension = 'completeness') AS bad_completeness,
           BOOL_OR(dimension = 'validity')     AS bad_validity,
           BOOL_OR(dimension = 'freshness')    AS bad_freshness
    FROM marts.dq_issues
    WHERE check_name NOT IN ('late_file', 'missing_file')
    GROUP BY source, date, record_id
),
late_files AS (                      -- record_id is NULL for a whole feed, or the entity for master data
    SELECT source, date, record_id AS entity FROM marts.dq_issues WHERE check_name = 'late_file'
),
scored AS (
    SELECT r.source, r.date, r.is_open_shipment,
           COALESCE(f.bad_completeness, FALSE) AS bad_completeness,
           COALESCE(f.bad_validity, FALSE)     AS bad_validity,
           COALESCE(f.bad_freshness, FALSE) OR l.source IS NOT NULL AS bad_freshness
    FROM marts.dq_records r
    LEFT JOIN record_flags f ON f.source = r.source AND f.date = r.date AND f.record_id = r.record_id
    LEFT JOIN late_files l ON NOT r.is_open_shipment AND l.source = r.source AND l.date = r.date
                          AND (l.entity IS NULL OR r.record_id LIKE l.entity || '/%')
),
calendar AS (                        -- every source x every day, so a day with no file still gets a row
    SELECT s.source, d.date
    FROM (SELECT DISTINCT source FROM raw.files) s
    CROSS JOIN (SELECT CAST(UNNEST(generate_series(MIN(file_date), MAX(file_date), INTERVAL 1 DAY)) AS DATE) AS date
                FROM raw.files) d
),
daily AS (
    SELECT c.source, c.date,
           COUNT(s.source) FILTER (WHERE NOT s.is_open_shipment) AS records,
           100.0 * COUNT(s.source) FILTER (WHERE NOT s.is_open_shipment AND NOT s.bad_completeness)
                 / NULLIF(COUNT(s.source) FILTER (WHERE NOT s.is_open_shipment), 0) AS completeness_pct,
           100.0 * COUNT(s.source) FILTER (WHERE NOT s.is_open_shipment AND NOT s.bad_validity)
                 / NULLIF(COUNT(s.source) FILTER (WHERE NOT s.is_open_shipment), 0) AS validity_pct,
           100.0 * COUNT(s.source) FILTER (WHERE NOT s.bad_freshness)
                 / NULLIF(COUNT(s.source), 0) AS freshness_measured
    FROM calendar c
    LEFT JOIN scored s ON s.source = c.source AND s.date = c.date
    GROUP BY c.source, c.date
),
with_freshness AS (
    SELECT d.*,
           CASE WHEN EXISTS (SELECT 1 FROM marts.dq_issues i
                             WHERE i.check_name = 'missing_file' AND i.source = d.source AND i.date = d.date) THEN 0
                WHEN d.freshness_measured IS NULL THEN 100
                ELSE d.freshness_measured END AS freshness_pct
    FROM daily d
)
SELECT w.date,
       w.source,
       w.records,
       ROUND(w.completeness_pct, 2) AS completeness_pct,
       ROUND(w.validity_pct, 2)     AS validity_pct,
       ROUND(w.freshness_pct, 2)    AS freshness_pct,
       ROUND((COALESCE(w.completeness_pct, 0) + COALESCE(w.validity_pct, 0) + w.freshness_pct)
             / (1 + (w.completeness_pct IS NOT NULL)::INTEGER + (w.validity_pct IS NOT NULL)::INTEGER), 2) AS dq_score,
       (SELECT COUNT(*) FROM marts.dq_issues i WHERE i.source = w.source AND i.date = w.date) AS issues
FROM with_freshness w
