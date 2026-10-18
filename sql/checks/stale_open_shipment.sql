-- freshness | an open shipment (shipped, not yet reported delivered) with no tracking update for more than 48 h at
-- the end of day D. Not planted directly: it follows from feed outages. One row per shipment per day it is stale,
-- dated D, so the carrier feed's freshness score drops on exactly the days the feed is silent.
SELECT 'carrier_tracking' AS source, as_of_date AS file_date, shipment_id AS record_id,
       'stale_open_shipment' AS check_name, 'freshness' AS dimension,
       'open shipment, last tracking update ' || CAST(ROUND(hours_since_update) AS INTEGER) || ' h before end of day' AS reason,
       dc_code
FROM staging.open_shipment_days
WHERE hours_since_update > 48
