-- The denominator of the DQ score: every record each source delivered on each day, one row per row received
-- (two copies of a duplicated master row are two records). For the carrier feed, the shipments that were open on a day
-- count too, but only towards freshness (is_open_shipment): they are what a silent feed makes stale.
SELECT 'erp_orders' AS source, file_date AS date, record_id, FALSE AS is_open_shipment FROM staging.erp_orders
UNION ALL
SELECT 'wms_shipments', file_date, record_id, FALSE FROM staging.wms_shipments
UNION ALL
SELECT 'carrier_tracking', file_date, record_id, FALSE FROM staging.carrier_events
UNION ALL
SELECT 'carrier_tracking', as_of_date, shipment_id, TRUE FROM staging.open_shipment_days
UNION ALL
SELECT 'master_data', file_date, record_id, FALSE FROM staging.customers
UNION ALL
SELECT 'master_data', file_date, record_id, FALSE FROM staging.products
UNION ALL
SELECT 'master_data', file_date, record_id, FALSE FROM staging.dcs
UNION ALL
SELECT 'master_data', file_date, record_id, FALSE FROM staging.carriers
