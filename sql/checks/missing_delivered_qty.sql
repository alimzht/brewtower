-- completeness | a DELIVERED event must say how much was delivered, or in-full cannot be measured.
SELECT 'carrier_tracking' AS source, e.file_date, e.record_id, 'missing_delivered_qty' AS check_name,
       'completeness' AS dimension, 'DELIVERED event without delivered_qty' AS reason, s.dc_code
FROM staging.carrier_events e
LEFT JOIN staging.shipments s ON s.shipment_id = e.shipment_id
WHERE e.status = 'DELIVERED' AND e.delivered_qty IS NULL
