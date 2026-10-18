-- validity | an event cannot happen after the file reporting it was extracted: the timestamp is in the future.
SELECT 'carrier_tracking' AS source, e.file_date, e.record_id, 'event_after_extraction' AS check_name,
       'validity' AS dimension, 'event_at ' || e.event_at || ' is after extracted_at ' || e.extracted_at AS reason,
       s.dc_code
FROM staging.carrier_events e
LEFT JOIN staging.shipments s ON s.shipment_id = e.shipment_id
WHERE e.event_at > e.extracted_at
