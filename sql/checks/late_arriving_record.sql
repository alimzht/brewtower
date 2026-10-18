-- freshness | an event that arrives in a later day's file than the day it happened (a feed outage being backfilled).
-- Events timestamped before dispatch are left out: their timestamp is wrong (delivered_before_shipped), not late.
SELECT 'carrier_tracking' AS source, e.file_date, e.record_id, 'late_arriving_record' AS check_name,
       'freshness' AS dimension,
       'event of ' || CAST(e.event_at AS DATE) || ' arrived in the file of ' || e.file_date AS reason, s.dc_code
FROM staging.carrier_events e
LEFT JOIN staging.shipments s ON s.shipment_id = e.shipment_id
WHERE CAST(e.event_at AS DATE) < e.file_date
  AND e.event_at >= COALESCE(s.shipped_at, e.event_at)
