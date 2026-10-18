-- For every day D: the shipments that have left a DC by D but whose DELIVERED event had not arrived in any carrier
-- file up to D. last_update = the newest tracking event received by D, or the WMS dispatch time if the carrier has
-- not reported anything yet. The stale_open_shipment check flags those not updated for more than 48 h at the end of D.
WITH days AS (
    SELECT CAST(UNNEST(generate_series(MIN(file_date), MAX(file_date), INTERVAL 1 DAY)) AS DATE) AS as_of_date
    FROM raw.files
),
delivered AS (
    SELECT shipment_id, MIN(file_date) AS delivered_reported_on
    FROM staging.carrier_events
    WHERE status = 'DELIVERED'
    GROUP BY shipment_id
),
open_days AS (
    SELECT d.as_of_date, s.shipment_id, s.dc_code, s.carrier_id, s.shipped_at
    FROM staging.shipments s
    JOIN days d ON d.as_of_date >= CAST(s.shipped_at AS DATE)
    LEFT JOIN delivered x ON x.shipment_id = s.shipment_id
    WHERE x.delivered_reported_on IS NULL OR x.delivered_reported_on > d.as_of_date
),
last_seen AS (
    SELECT o.as_of_date, o.shipment_id, o.dc_code, o.carrier_id,
           GREATEST(o.shipped_at, MAX(e.event_at)) AS last_update        -- GREATEST ignores NULLs
    FROM open_days o
    LEFT JOIN staging.carrier_events e ON e.shipment_id = o.shipment_id AND e.file_date <= o.as_of_date
    GROUP BY o.as_of_date, o.shipment_id, o.dc_code, o.carrier_id, o.shipped_at
)
SELECT *,
       date_diff('minute', last_update, as_of_date + INTERVAL 1 DAY) / 60.0 AS hours_since_update
FROM last_seen
