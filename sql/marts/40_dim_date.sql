-- Calendar covering every date the facts and DQ tables use (including the odd invalid-but-parseable one).
WITH bounds AS (
    SELECT LEAST((SELECT MIN(order_date) FROM marts.fact_orders),
                 (SELECT MIN(promised_date) FROM marts.fact_orders),
                 (SELECT MIN(date) FROM marts.dq_score_daily)) AS first_day,
           GREATEST((SELECT MAX(promised_date) FROM marts.fact_orders),
                    (SELECT MAX(delivery_date) FROM marts.fact_deliveries),
                    (SELECT MAX(date) FROM marts.dq_score_daily)) AS last_day
),
days AS (
    SELECT CAST(UNNEST(generate_series(first_day, last_day, INTERVAL 1 DAY)) AS DATE) AS date FROM bounds
)
SELECT date,
       year(date)                                       AS year,
       month(date)                                      AS month,
       strftime(date, '%B')                             AS month_name,
       CAST(date_trunc('month', date) AS DATE)          AS month_start,
       CAST(date_trunc('week', date) AS DATE)           AS week_start,     -- Monday (ISO week)
       weekofyear(date)                                 AS iso_week,
       isodow(date)                                     AS weekday_no,     -- 1 = Monday
       strftime(date, '%A')                             AS weekday_name,
       isodow(date) >= 6                                AS is_weekend
FROM days
