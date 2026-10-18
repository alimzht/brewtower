-- Weekly delivery KPIs by DC and carrier, over KPI-eligible orders, by the week of the promised date.
-- Power BI computes the same numbers from fact_deliveries with DAX; this table is for the README and the tests.
SELECT CAST(date_trunc('week', promised_date) AS DATE)                AS week_start,
       dc_code,
       carrier_id,
       COUNT(*)                                                       AS shipments,
       COUNT(*) FILTER (WHERE is_on_time)                             AS on_time,
       COUNT(*) FILTER (WHERE is_otif)                                AS otif,
       COUNT(*) FILTER (WHERE NOT is_on_time)                         AS late,
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_on_time) / COUNT(*), 2) AS otd_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_otif) / COUNT(*), 2)    AS otif_pct,
       ROUND(AVG(delay_days), 3)                                      AS avg_delay_days
FROM marts.fact_deliveries
WHERE kpi_eligible
GROUP BY ALL
