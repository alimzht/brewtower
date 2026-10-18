-- validity | cross-source: the carrier cannot deliver before the WMS shipped (usually a carrier clock problem).
SELECT 'carrier_tracking' AS source, e.file_date, e.record_id, 'delivered_before_shipped' AS check_name,
       'validity' AS dimension, 'delivered ' || e.event_at || ', shipped ' || s.shipped_at AS reason, s.dc_code
FROM staging.carrier_events e
JOIN staging.shipments s ON s.shipment_id = e.shipment_id
WHERE e.status = 'DELIVERED' AND e.event_at < s.shipped_at
