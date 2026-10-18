-- One row per order line as entered in SAP, with what the WMS shipped against it. Lines with data-quality issues are
-- kept and flagged (has_dq_issue); keys that do not match a dimension point at its UNKNOWN member.
WITH shipped AS (
    SELECT order_id, order_line, MIN(shipment_id) AS shipment_id, SUM(shipped_qty) AS shipped_qty
    FROM staging.wms_shipments
    GROUP BY order_id, order_line
),
flagged AS (
    SELECT DISTINCT record_id FROM marts.dq_issues WHERE source = 'erp_orders'
)
SELECT o.order_id,
       o.order_line,
       o.record_id                                     AS order_line_key,
       o.order_date,
       o.promised_date,
       COALESCE(c.customer_id, -1)                     AS customer_id,
       COALESCE(k.sku, 'UNKNOWN')                      AS sku,
       COALESCE(d.dc_code, 'UNKNOWN')                  AS dc_code,
       o.ordered_qty,
       s.shipment_id,
       s.shipped_qty,
       s.shipped_qty < o.ordered_qty                   AS is_short_shipped,
       f.record_id IS NOT NULL                         AS has_dq_issue
FROM staging.erp_orders o
LEFT JOIN marts.dim_customer c ON c.customer_id = o.customer_id AND c.customer_id <> -1
LEFT JOIN marts.dim_sku k ON k.sku = o.sku AND k.sku <> 'UNKNOWN'
LEFT JOIN marts.dim_dc d ON d.dc_code = o.dc_code AND d.dc_code <> 'UNKNOWN'
LEFT JOIN shipped s ON s.order_id = o.order_id AND s.order_line = o.order_line
LEFT JOIN flagged f ON f.record_id = o.record_id
