-- One row per order (= one shipment): promised vs actual, and the delivery KPIs.
--   is_on_time  delivered on or before the promised date
--   is_in_full  every line shipped in full AND the carrier delivered everything that was shipped
--   is_otif     both
--   delay_days  days after the promised date (0 when on time)
--   late_cause  dc_dispatch_delay if it left the DC after the promised date, else carrier_delay
--   kpi_eligible  delivered, has a valid promised date, and no completeness/validity issue on a field the KPI uses
--                 (promised date, quantities, the DELIVERED event). OTD/OTIF are computed over eligible orders only.
--   An unknown customer, SKU or DC does not block the KPI: the order counts, under the UNKNOWN member.
WITH orders AS (
    SELECT order_id,
           MIN(order_date)                                        AS order_date,
           MIN(promised_date)                                     AS promised_date,
           MIN(customer_id)                                       AS customer_id,
           MIN(dc_code) FILTER (WHERE dc_code <> 'UNKNOWN')       AS dc_code,
           SUM(ordered_qty) FILTER (WHERE ordered_qty > 0)        AS ordered_qty,
           BOOL_AND(COALESCE(shipped_qty, 0) >= ordered_qty)      AS all_lines_full,
           BOOL_OR(has_dq_issue)                                  AS line_issue
    FROM marts.fact_orders
    GROUP BY order_id
),
delivered AS (
    SELECT shipment_id, MIN(event_at) AS delivered_at, MIN(delivered_qty) AS delivered_qty,
           MIN(carrier_id) AS carrier_id
    FROM staging.carrier_events
    WHERE status = 'DELIVERED'
    GROUP BY shipment_id
),
kpi_blockers AS (                    -- orders whose KPI inputs are missing or invalid
    SELECT o.order_id FROM marts.dq_issues i JOIN staging.erp_orders o ON o.record_id = i.record_id
    WHERE i.source = 'erp_orders'
      AND i.check_name IN ('missing_promised_date', 'invalid_date', 'promised_before_ordered', 'nonpositive_qty')
    UNION
    SELECT w.order_id FROM marts.dq_issues i JOIN staging.wms_shipments w ON w.record_id = i.record_id
    WHERE i.source = 'wms_shipments' AND i.check_name = 'nonpositive_qty'
    UNION
    SELECT s.order_id FROM marts.dq_issues i
    JOIN staging.carrier_events e ON e.record_id = i.record_id
    JOIN staging.shipments s ON s.shipment_id = e.shipment_id
    WHERE i.source = 'carrier_tracking'
      AND i.check_name IN ('missing_delivered_qty', 'delivered_before_shipped', 'event_after_extraction')
),
shipment_issues AS (                 -- any record-level issue on the shipment's WMS lines, events or open-shipment days
    SELECT DISTINCT w.shipment_id FROM marts.dq_issues i JOIN staging.wms_shipments w ON w.record_id = i.record_id
    WHERE i.source = 'wms_shipments'
    UNION
    SELECT DISTINCT e.shipment_id FROM marts.dq_issues i JOIN staging.carrier_events e ON e.record_id = i.record_id
    WHERE i.source = 'carrier_tracking'
    UNION
    SELECT DISTINCT record_id FROM marts.dq_issues WHERE check_name = 'stale_open_shipment'
),
joined AS (
    SELECT o.*, s.shipment_id, s.shipped_at, s.shipped_qty, s.dc_code AS wms_dc_code, s.carrier_id AS wms_carrier_id,
           d.delivered_at, CAST(d.delivered_at AS DATE) AS delivery_date, d.delivered_qty,
           d.carrier_id AS tracking_carrier_id
    FROM orders o
    LEFT JOIN staging.shipments s ON s.order_id = o.order_id
    LEFT JOIN delivered d ON d.shipment_id = s.shipment_id
)
SELECT j.order_id,
       j.shipment_id,
       j.customer_id,
       COALESCE(j.dc_code, j.wms_dc_code, 'UNKNOWN')                                  AS dc_code,
       COALESCE(cw.carrier_id, ct.carrier_id, 'UNKNOWN')                              AS carrier_id,
       j.order_date,
       j.promised_date,
       j.shipped_at,
       j.delivered_at,
       j.delivery_date,
       j.ordered_qty,
       j.shipped_qty,
       j.delivered_qty,
       j.delivered_at IS NOT NULL                                                     AS is_delivered,
       j.delivery_date <= j.promised_date                                             AS is_on_time,
       j.all_lines_full AND j.delivered_qty >= j.shipped_qty                          AS is_in_full,
       j.delivery_date <= j.promised_date AND j.all_lines_full AND j.delivered_qty >= j.shipped_qty AS is_otif,
       GREATEST(0, date_diff('day', j.promised_date, j.delivery_date))                AS delay_days,
       CASE WHEN j.delivery_date > j.promised_date THEN
                CASE WHEN CAST(j.shipped_at AS DATE) > j.promised_date THEN 'dc_dispatch_delay' ELSE 'carrier_delay' END
       END                                                                            AS late_cause,
       j.delivered_at IS NOT NULL AND j.promised_date IS NOT NULL AND b.order_id IS NULL AS kpi_eligible,
       j.line_issue OR si.shipment_id IS NOT NULL                                     AS has_dq_issue
FROM joined j
LEFT JOIN marts.dim_carrier cw ON cw.carrier_id = j.wms_carrier_id AND cw.carrier_id <> 'UNKNOWN'
LEFT JOIN marts.dim_carrier ct ON ct.carrier_id = j.tracking_carrier_id AND ct.carrier_id <> 'UNKNOWN'
LEFT JOIN (SELECT DISTINCT order_id FROM kpi_blockers) b ON b.order_id = j.order_id
LEFT JOIN shipment_issues si ON si.shipment_id = j.shipment_id
