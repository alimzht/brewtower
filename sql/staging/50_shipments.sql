-- One row per shipment (one shipment = one order). The WMS repeats the header on every line, so a mistyped DC code
-- or a missing carrier on one line does not move the shipment: take the valid value from the other lines.
SELECT
    shipment_id,
    MIN(order_id)                                           AS order_id,
    MIN(shipped_at)                                         AS shipped_at,
    MIN(dc_code) FILTER (WHERE dc_code IN (SELECT dc_code FROM staging.dcs)) AS dc_code,
    MIN(carrier_id)                                         AS carrier_id,      -- MIN skips NULLs
    SUM(shipped_qty) FILTER (WHERE shipped_qty > 0)         AS shipped_qty
FROM staging.wms_shipments
GROUP BY shipment_id
