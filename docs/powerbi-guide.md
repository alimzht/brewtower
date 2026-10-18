# Power BI guide: building the BrewTower dashboard

This guide builds the two-page dashboard from the gold CSVs in `data/gold/`. It assumes Power BI Desktop
(free, Windows) and no earlier Power BI experience. It takes about two hours the first time.

Before you start, run the pipeline once so the CSVs are current:

```powershell
python -m brewtower.pipeline
```

At the end there is a checklist of numbers your visuals should show. If they match, the model is right.

---

## 1. Settings before importing

1. **File → Options and settings → Options → Current file → Regional settings.**
   Set **Locale for import** to **English (United States)**. The CSVs use `.` as the decimal separator and
   `YYYY-MM-DD` dates. With a Czech locale, Power BI would read `97.33` as text or as 9733.
2. Same dialog, **Current file → Data load**: untick **Auto date/time**. We have our own date table
   (`dim_date`), and the automatic hidden date tables only add size and confusion.

## 2. Import the CSVs

For each file below: **Home → Get data → Text/CSV**, pick the file, then click **Transform data** (not Load) so
you can check the column types in Power Query. In Power Query, click the icon left of each column name to change
its type. Then **Home → Close & Apply**.

Import these 9 files. Skip `delivery_kpis.csv`: it is a pre-aggregated table for the README and the tests;
in Power BI the same numbers come from DAX measures.

| Table | Set these types (everything else: Text) |
|---|---|
| `fact_deliveries` | `order_id`, `customer_id`, `ordered_qty`, `shipped_qty`, `delivered_qty`, `delay_days`: Whole number. `order_date`, `promised_date`, `delivery_date`: Date. `shipped_at`, `delivered_at`: Date/Time. `is_delivered`, `is_on_time`, `is_in_full`, `is_otif`, `kpi_eligible`, `has_dq_issue`: True/False |
| `fact_orders` | `order_id`, `order_line`, `customer_id`, `ordered_qty`, `shipped_qty`: Whole number. `order_date`, `promised_date`: Date. `is_short_shipped`, `has_dq_issue`: True/False. Keep `order_line_key` as Text |
| `dim_customer` | `customer_id`: Whole number. `first_seen`, `valid_from`: Date |
| `dim_sku` | `liters_per_pack`: Decimal number. `launched_on`: Date |
| `dim_dc` | all Text |
| `dim_carrier` | all Text |
| `dim_date` | `date`, `month_start`, `week_start`: Date. `year`, `month`, `iso_week`, `weekday_no`: Whole number. `is_weekend`: True/False |
| `dq_issues` | `date`: Date. `record_id` must stay **Text** (it looks like a number on some rows) |
| `dq_score_daily` | `date`: Date. `records`, `issues`: Whole number. `completeness_pct`, `validity_pct`, `freshness_pct`, `dq_score`: Decimal number |

Empty cells (for example `completeness_pct` on a day with no file) must stay empty (`null`), not 0. That is
on purpose: a day with no file has nothing to measure for completeness.

### One small table you type in: `dim_source`

`dq_score_daily` and `dq_issues` both have a `source` column. To let one slicer filter both, they need a shared
table. **Home → Enter data**, name it `dim_source`, one column `source`, four rows:

```
erp_orders
wms_shipments
carrier_tracking
master_data
```

### A table for the measures: `_Measures`

**Home → Enter data**, name it `_Measures`, leave the one column, click Load. After you add the first measure
(section 4) to it, delete `Column1`. Power BI then shows it at the top of the Fields list with a calculator icon.

## 3. Model: relationships and the date table

Open **Model view** (left bar, third icon). Delete any relationship Power BI guessed on its own, then create these
by dragging the column from the first table onto the column in the second. In the dialog check the cardinality
and the cross-filter direction.

| # | From (many side) | To (one side) | Cardinality | Cross-filter | Active |
|---|---|---|---|---|---|
| 1 | `fact_deliveries[promised_date]` | `dim_date[date]` | many-to-one | single | yes |
| 2 | `fact_deliveries[delivery_date]` | `dim_date[date]` | many-to-one | single | **no** (inactive) |
| 3 | `fact_deliveries[dc_code]` | `dim_dc[dc_code]` | many-to-one | single | yes |
| 4 | `fact_deliveries[carrier_id]` | `dim_carrier[carrier_id]` | many-to-one | single | yes |
| 5 | `fact_deliveries[customer_id]` | `dim_customer[customer_id]` | many-to-one | single | yes |
| 6 | `fact_orders[order_date]` | `dim_date[date]` | many-to-one | single | yes |
| 7 | `fact_orders[dc_code]` | `dim_dc[dc_code]` | many-to-one | single | yes |
| 8 | `fact_orders[customer_id]` | `dim_customer[customer_id]` | many-to-one | single | yes |
| 9 | `fact_orders[sku]` | `dim_sku[sku]` | many-to-one | single | yes |
| 10 | `dq_score_daily[date]` | `dim_date[date]` | many-to-one | single | yes |
| 11 | `dq_score_daily[source]` | `dim_source[source]` | many-to-one | single | yes |
| 12 | `dq_issues[date]` | `dim_date[date]` | many-to-one | single | yes |
| 13 | `dq_issues[source]` | `dim_source[source]` | many-to-one | single | yes |
| 14 | `dq_issues[dc_code]` | `dim_dc[dc_code]` | many-to-one | single | yes |

Why it looks like this:

- **Delivery KPIs are dated by the promised date** (relationship 1). "July OTD" means orders promised for July.
  Relationship 2 stays inactive; a measure can switch to it with `USERELATIONSHIP` (see "Deliveries (by delivery
  date)" below). Power BI allows only one active path between two tables.
- **The two fact tables are not related to each other.** They share dimensions instead. That keeps every filter
  path single and unambiguous.
- **Every key in the facts exists in its dimension.** The pipeline adds an "Unknown" member to each dimension
  (`customer_id = -1`, `dc_code = UNKNOWN`, `carrier_id = UNKNOWN`), so orders with a bad code still show up,
  under "Unknown", instead of disappearing.
- **The DC slicer filters issues, not the score.** `dq_score_daily` is per source per day and has no DC column.
  To see a DC's data quality, look at its issues (relationship 14).

**Mark the date table:** select `dim_date` → **Table tools → Mark as date table** → column `date`.

**Sort month names:** select `dim_date[month_name]` → **Column tools → Sort by column → month**. Do the same for
`weekday_name` by `weekday_no`.

**Hide the keys** on the fact side (right-click → Hide in report view): `fact_deliveries[dc_code]`,
`[carrier_id]`, `[customer_id]`, `fact_orders[dc_code]`, `[customer_id]`, `[sku]`, the `date` and `source`
columns of `dq_score_daily` and `dq_issues`. You then always slice by the dimension columns, which is what makes
the relationships work.

## 4. DAX measures

Select `_Measures` → **New measure**, paste one measure at a time. Set the format in **Measure tools**: `%`
measures as Percentage with 1 decimal, counts as Whole number with thousands separator, delay with 2 decimals.

### Delivery measures

```dax
Shipments = COUNTROWS ( fact_deliveries )
```
All orders (one order = one shipment), including undelivered and blocked ones.

```dax
Shipments Eligible =
CALCULATE ( COUNTROWS ( fact_deliveries ), fact_deliveries[kpi_eligible] = TRUE () )
```
The KPI denominator: delivered, valid promised date, no data issue on a field the KPI uses.

```dax
On Time =
CALCULATE (
    COUNTROWS ( fact_deliveries ),
    fact_deliveries[kpi_eligible] = TRUE (),
    fact_deliveries[is_on_time] = TRUE ()
)
```
Eligible shipments delivered on or before the promised date.

```dax
OTD % = DIVIDE ( [On Time], [Shipments Eligible] )
```
On-time delivery rate. `DIVIDE` returns blank instead of an error when there are no shipments.

```dax
OTIF % =
DIVIDE (
    CALCULATE (
        COUNTROWS ( fact_deliveries ),
        fact_deliveries[kpi_eligible] = TRUE (),
        fact_deliveries[is_otif] = TRUE ()
    ),
    [Shipments Eligible]
)
```
On time and in full. `is_otif` is computed in SQL, so the definition lives in one place.

```dax
In Full % =
DIVIDE (
    CALCULATE (
        COUNTROWS ( fact_deliveries ),
        fact_deliveries[kpi_eligible] = TRUE (),
        fact_deliveries[is_in_full] = TRUE ()
    ),
    [Shipments Eligible]
)
```
Every line shipped in full and everything shipped was delivered, whatever the timing.

```dax
Avg Delay (Days) =
CALCULATE ( AVERAGE ( fact_deliveries[delay_days] ), fact_deliveries[kpi_eligible] = TRUE () )
```
Average days late; on-time shipments count as 0, so this mixes how often and how badly.

```dax
Late Deliveries = [Shipments Eligible] - [On Time]
```
Eligible shipments that arrived after the promised date.

```dax
Late Share % = DIVIDE ( [Late Deliveries], CALCULATE ( [Late Deliveries], ALLSELECTED () ) )
```
Each row's share of all late deliveries in the current selection. `ALLSELECTED()` removes the visual's own row
filter (carrier, DC…) but keeps the slicers, so the rows of a carrier table add up to 100 %.

```dax
Deliveries (by delivery date) =
CALCULATE (
    COUNTROWS ( fact_deliveries ),
    fact_deliveries[is_delivered] = TRUE (),
    USERELATIONSHIP ( fact_deliveries[delivery_date], dim_date[date] )
)
```
Shipments counted on the day they arrived, using the inactive relationship 2. Useful for workload per day.

```dax
Short-Shipped Lines % =
DIVIDE (
    CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[is_short_shipped] = TRUE () ),
    CALCULATE ( COUNTROWS ( fact_orders ), NOT ISBLANK ( fact_orders[shipped_qty] ) )
)
```
Order lines where the DC shipped less than ordered, out of lines that were shipped. Dated by order date.

### Data-quality measures

```dax
DQ Score % = DIVIDE ( AVERAGE ( dq_score_daily[dq_score] ), 100 )
```
Average of the daily scores. `dq_score` is 0 to 100 in the CSV; dividing by 100 lets Power BI format it as %.

**Why the average of days, not of records?** Every day counts once. A day when the carrier sent no file has
0 records; weighted by records it would weigh nothing, and a three-day outage would barely move the score.
Averaging days makes a missing day hurt as much as it should. The records-weighted version is below for
comparison only.

```dax
DQ Score % (records-weighted) =
VAR c = DIVIDE ( SUMX ( dq_score_daily, dq_score_daily[completeness_pct] * dq_score_daily[records] ), SUM ( dq_score_daily[records] ) )
VAR v = DIVIDE ( SUMX ( dq_score_daily, dq_score_daily[validity_pct] * dq_score_daily[records] ), SUM ( dq_score_daily[records] ) )
VAR f = DIVIDE ( SUMX ( dq_score_daily, dq_score_daily[freshness_pct] * dq_score_daily[records] ), SUM ( dq_score_daily[records] ) )
RETURN DIVIDE ( c + v + f, 300 )
```
Same three dimensions, but busy days count more. Don't use it as the headline.

```dax
Completeness % = DIVIDE ( AVERAGE ( dq_score_daily[completeness_pct] ), 100 )
```
```dax
Validity % = DIVIDE ( AVERAGE ( dq_score_daily[validity_pct] ), 100 )
```
```dax
Freshness % = DIVIDE ( AVERAGE ( dq_score_daily[freshness_pct] ), 100 )
```
The three parts of the score. `AVERAGE` skips empty cells, so a day with no file counts for freshness (as 0)
but not for completeness or validity, exactly like the SQL.

```dax
Records Checked = SUM ( dq_score_daily[records] )
```
Rows received from the sources in the selection.

```dax
Issues = COUNTROWS ( dq_issues )
```
Failing records (one row per record per check). There is no open/closed status: this is a log of what failed.
Put `dq_issues[check_name]` on an axis to get issues by check.

```dax
Stale Open Shipments =
CALCULATE ( [Issues], dq_issues[check_name] = "stale_open_shipment" )
```
Shipment-days with no tracking update for more than 48 h. These come from feed outages, not from bad rows.

```dax
Issues excl. Stale = [Issues] - [Stale Open Shipments]
```
Record-level defects only. Over the full period this equals the 2,427 planted defects.

```dax
Days Below 95 =
COUNTROWS ( FILTER ( dq_score_daily, dq_score_daily[dq_score] < 95 ) )
```
Source-days that would have triggered an alert at a threshold of 95.

```dax
Lowest Daily Score % = DIVIDE ( MIN ( dq_score_daily[dq_score] ), 100 )
```
The worst source-day in the selection.

## 5. Theme

**View → Themes → Browse for themes** → pick `docs/copper-tower-theme.json`. Colours: Copper `#A3480F`,
Espresso `#2B1A12`, Malt Gold `#D9A441`, Foam `#FBF7F1` as the page background, plus a few brand neutrals and
green/red for good/bad. Malt Gold is too light for text on Foam; use it only for bars and fills.

## 6. Page 1: "Data quality"

Rename the first page tab **Data quality**. Suggested layout: slicers along the top, cards below them, the line
chart across the middle, two charts at the bottom.

| Visual | Type | Fields | Question it answers |
|---|---|---|---|
| Date slicer | Slicer (Between) | `dim_date[date]` | Which period am I looking at? |
| Source slicer | Slicer (Dropdown or tiles) | `dim_source[source]` | Which system? |
| DC slicer | Slicer (Dropdown) | `dim_dc[dc_name]` | Which DC's issues? (filters issues only, see section 3) |
| Score cards | 5 Cards | `DQ Score %`, `Completeness %`, `Validity %`, `Freshness %`, `Issues` | How good is the data overall, and which dimension pulls it down? |
| Score over time | Line chart | X: `dim_date[date]`; Y: `DQ Score %`; Legend: `dim_source[source]` | Which source dropped, and on which day? |
| Breakdown | Matrix | Rows: `dim_source[source]`; Values: `Completeness %`, `Validity %`, `Freshness %`, `DQ Score %`, `Days Below 95` | Why is a source's score what it is? Add conditional formatting (background colour, red under 95 %) |
| Top failing checks | Clustered bar chart | Y: `dq_issues[check_name]`; X: `Issues`; Legend: `dq_issues[dimension]`; sort by `Issues` descending | Which rules fail most? |
| Freshness by DC | Clustered column chart | X: `dim_dc[dc_name]`; Y: `Issues`; visual filter: `dq_issues[dimension]` is `freshness` | Where are the stale shipments? (Brno stands out) |

### Drill-through page "Issue details"

1. Add a new page, name it **Issue details**.
2. Add a **Table** with `dim_date[date]`, `dim_source[source]`, `dq_issues[check_name]`, `dq_issues[dimension]`,
   `dq_issues[record_id]`, `dim_dc[dc_name]`, `dq_issues[reason]`. (Date and source come from the dimensions
   because you hid the fact-side columns in section 3.)
3. In the **Visualizations** pane, under **Drill through**, add `dim_source[source]`, `dim_date[date]` and
   `dq_issues[check_name]`. Leave **Keep all filters** on. Power BI adds a back button automatically.
4. Test it: on page 1, right-click the low point of the carrier_tracking line on 15 May → **Drill through →
   Issue details**. You should see the 497 `late_arriving_record` rows of that day, each with its reason.

This is the "why is it 77?" path: score → dimension breakdown → the exact records and reasons.

## 7. Page 2: "Delivery performance"

Add a page named **Delivery performance**.

| Visual | Type | Fields | Question it answers |
|---|---|---|---|
| Date slicer | Slicer (Between) | `dim_date[date]` (= promised date) | Which period? |
| DC / carrier / customer type | 3 Slicers (Dropdown) | `dim_dc[dc_name]`, `dim_carrier[carrier_name]`, `dim_customer[customer_type]` | Narrow down to one part of the network |
| KPI cards | 6 Cards | `OTD %`, `OTIF %`, `In Full %`, `Avg Delay (Days)`, `Late Deliveries`, `Shipments Eligible` | How are we doing? |
| Weekly trend | Line chart | X: `dim_date[week_start]`; Y: `OTD %`, `OTIF %` | Is it getting better or worse, and when did it change? |
| By carrier | Clustered bar chart | Y: `dim_carrier[carrier_name]`; X: `OTD %`, `OTIF %` | Which carrier is weakest? |
| Share of late | Clustered bar chart (or donut) | Y: `dim_carrier[carrier_name]`; X: `Late Share %` | Who causes the late deliveries? |
| Root cause | Stacked bar chart | Y: `dim_carrier[carrier_name]`; X: `Late Deliveries`; Legend: `fact_deliveries[late_cause]` | Was it the carrier or the DC dispatch? |
| DC × month | Matrix | Rows: `dim_dc[dc_name]`; Columns: `dim_date[month_name]`; Values: `OTIF %`; conditional formatting | Which DC had a bad month? |
| Can shortage | Clustered column chart | X: `dim_date[month_name]`; Y: `Short-Shipped Lines %`; Legend: `dim_sku[pack]` | Did any pack type run short? (cans in July) |

In the root-cause chart, blank `late_cause` means the shipment was on time; add a visual filter
`fact_deliveries[late_cause]` is not blank.

## 8. Checklist: values your visuals should show

Full period, no slicers selected. If a number differs, check the types (section 2) and the relationships
(section 3) first.

**Page 2, delivery**

| Measure | Expected |
|---|---|
| Shipments | 16,835 |
| Shipments Eligible | 16,224 |
| On Time | 14,474 |
| OTD % | 89.2 % |
| OTIF % | 80.6 % |
| In Full % | 90.3 % |
| Avg Delay (Days) | 0.20 |
| Late Deliveries | 1,750 |

| Carrier | OTD % | OTIF % | Late Share % |
|---|---|---|---|
| Vltava Freight (CR01) | 94.0 % | 85.2 % | 19.7 % |
| Moravia Express (CR02) | 93.6 % | 83.6 % | 10.6 % |
| TransBohemia (CR03) | 78.5 % | 71.2 % | 61.7 % |
| Silesia Logistics (CR04) | 94.5 % | 85.1 % | 8.0 % |

Root cause, all carriers: 1,453 `carrier_delay`, 297 `dc_dispatch_delay`. TransBohemia alone: 987 and 92.

| DC | OTD % | OTIF % |
|---|---|---|
| DC Prague | 88.3 % | 79.6 % |
| DC Brno | 89.1 % | 80.1 % |
| DC Ostrava | 94.2 % | 84.0 % |
| DC Plzen | 84.9 % | 76.5 % |
| DC Ceske Budejovice | 85.7 % | 79.0 % |
| DC Hradec Kralove | 94.1 % | 85.8 % |

OTIF % by customer type: bar 83.4 %, retailer 76.3 %, wholesaler 72.7 %, unknown 84.5 %.

OTIF % by promised month: July 75.5 %; the other months 81.6 % to 82.6 %. In Full % in July: 85.1 %.

Short-Shipped Lines % for CAN24 in July: 14.6 % (373 of 2,563 lines); other months 2.7 % to 3.8 %.

**Page 1, data quality**

| Measure | Expected |
|---|---|
| DQ Score % | 98.3 % |
| Completeness % | 99.6 % |
| Validity % | 99.1 % |
| Freshness % | 96.8 % |
| DQ Score % (records-weighted) | 98.5 % |
| Records Checked | 129,088 |
| Issues | 5,284 |
| Stale Open Shipments | 2,857 |
| Issues excl. Stale | 2,427 |
| Days Below 95 | 39 |

| Source | DQ Score % | Days Below 95 |
|---|---|---|
| carrier_tracking | 95.6 % | 30 |
| erp_orders | 98.8 % | 4 |
| master_data | 99.5 % | 3 |
| wms_shipments | 99.5 % | 2 |

Spot checks on the line chart (source = carrier_tracking): 12, 13 and 14 May are 0 %; 15 May is 77.3 %;
in August it drops to 72.3 % on 8 August and stays low until 27 August (75.7 %), then is back to 99.9 % on
28 August. With DC = DC Brno, month = August and `dq_issues[dimension]` = freshness, `Issues` shows 3,393
(2,776 stale shipment-days + 617 late-arriving events).
