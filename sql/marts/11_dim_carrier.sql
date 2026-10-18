-- Carriers, plus an UNKNOWN member for shipments whose carrier is missing in every source.
SELECT carrier_id, ANY_VALUE(carrier_name ORDER BY file_date DESC) AS carrier_name
FROM staging.carriers
GROUP BY carrier_id
UNION ALL
SELECT 'UNKNOWN', 'Unknown carrier'
