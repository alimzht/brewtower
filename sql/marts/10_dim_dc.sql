-- Distribution centres, plus an UNKNOWN member so facts with an invalid DC code still join in Power BI.
SELECT dc_code, ANY_VALUE(dc_name ORDER BY file_date DESC) AS dc_name, ANY_VALUE(city ORDER BY file_date DESC) AS city
FROM staging.dcs
GROUP BY dc_code
UNION ALL
SELECT 'UNKNOWN', 'Unknown DC', NULL
