"""Generate six months of synthetic beer-distribution data, with planted defects, as raw daily files.

    python -m brewtower.generate

Breweries -> 6 distribution centres (DCs) -> ~400 bars, retailers and wholesalers, 2026-03-01 .. 2026-08-31.
Four sources, one CSV per source per day, shaped like the systems they imitate:
  data/raw/erp_orders/YYYY-MM-DD.csv              SAP-style order lines (VBELN, POSNR, KUNNR, MATNR, KWMENG, VDATU, WERKS)
  data/raw/wms_shipments/YYYY-MM-DD.csv           what left which DC, how much, with which carrier
  data/raw/carrier_tracking/YYYY-MM-DD.csv        carrier status events: PICKED_UP, IN_TRANSIT, DELIVERED
  data/raw/master_data/<entity>/YYYY-MM-DD.csv    customers, products, dcs, carriers: full load on day 1, then deltas
  data/raw/_planted_defects.csv                   answer key: every defect planted on purpose (the tests read it)

Some mess is normal and must be standardised, not flagged: SAP zero padding and "12.000" quantities, lowercase
DC codes with spaces in the WMS, lowercase statuses from one carrier. Stale open shipments (no tracking update for
> 48 h) are not in the answer key: they follow from the feed outages and the pipeline derives them per day.
Everything is synthetic and the seed is fixed, so every run writes the same files.
"""
import shutil
from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd

from brewtower.paths import RAW

SEED = 42
START, END = date(2026, 3, 1), date(2026, 8, 31)
DAYS = [START + timedelta(days=i) for i in range((END - START).days + 1)]

DCS = {"CZ01": "Prague", "CZ02": "Brno", "CZ03": "Ostrava", "CZ04": "Plzen", "CZ05": "Ceske Budejovice",
       "CZ06": "Hradec Kralove"}
DC_SHARE = [0.30, 0.20, 0.15, 0.13, 0.10, 0.12]           # share of customers served by each DC
CARRIERS = {"CR01": "Vltava Freight", "CR02": "Moravia Express", "CR03": "TransBohemia", "CR04": "Silesia Logistics"}
CARRIER_MIX = {"CZ01": {"CR01": .6, "CR03": .4}, "CZ02": {"CR02": .7, "CR03": .3}, "CZ03": {"CR04": .7, "CR02": .3},
               "CZ04": {"CR03": .6, "CR01": .4}, "CZ05": {"CR01": .5, "CR03": .5}, "CZ06": {"CR04": .5, "CR01": .5}}
LATE_PROB = {"CR01": .04, "CR02": .05, "CR03": .20, "CR04": .04}   # TransBohemia is the weak carrier
DC_DELAY_PROB = .02       # order dispatched a day after the promised date
DAMAGE_PROB = .015        # a pack or two broken on the way

BREWERIES = ["Copper Tower Brewery", "Moravian Hills Brewery", "Bohemian Highlands Brewery"]
BRANDS = [  # code, name, brewery index, popularity weight
    ("CL", "Copper Lager", 0, .20), ("TP", "Tower Pils", 0, .16), ("ES", "Espresso Stout", 0, .06),
    ("MG", "Malt Gold 12", 1, .12), ("HV", "Hop Valley Pale", 1, .08), ("ND", "Night Shift Dark", 1, .06),
    ("GA", "Granary Amber", 1, .06), ("FI", "Foam IPA", 2, .10), ("ZL", "Zero Lager 0.0", 2, .07),
    ("SW", "Summer Wheat", 2, .09)]
PACKS = {"BTL20": ("crate 20 x 0.5 l bottles", 10.0), "CAN24": ("tray 24 x 0.5 l cans", 12.0),
         "KEG30": ("keg 30 l", 30.0), "KEG50": ("keg 50 l", 50.0)}
SUMMER_WHEAT_LAUNCH = date(2026, 5, 15)

TYPE_SHARE = {"bar": .5, "retailer": .4, "wholesaler": .1}
ORDER_RATE = {"bar": .30, "retailer": .15, "wholesaler": .28}             # orders per customer per day, before factors
WEEKDAY = [1.0, .9, 1.0, 1.3, 1.45, .5, .1]                                  # Mon..Sun
LEAD_DAYS = {"bar": 1, "retailer": 2, "wholesaler": 3}
LINES = {"bar": (1, 4), "retailer": (2, 6), "wholesaler": (3, 9)}          # numpy integers(lo, hi): hi exclusive
QTY = {"bar": (1, 8), "retailer": (4, 32), "wholesaler": (30, 151)}
PACK_PREF = {"bar": {"KEG50": .45, "KEG30": .35, "BTL20": .15, "CAN24": .05},
             "retailer": {"CAN24": .55, "BTL20": .45},
             "wholesaler": {"KEG50": .25, "KEG30": .25, "BTL20": .25, "CAN24": .25}}
SURNAMES = ["Novak", "Svoboda", "Dvorak", "Cerny", "Prochazka", "Kucera", "Vesely", "Horak", "Nemec", "Marek",
            "Pospisil", "Hajek", "Jelinek", "Kral", "Ruzicka", "Benes", "Fiala", "Sedlacek", "Dolezal", "Zeman"]
NAME_STYLE = {"bar": ["Pub {}", "Bar {}", "Tavern {}", "Beer Hall {}", "Bistro {}"],
              "retailer": ["{} Market", "{} Grocery", "Minimarket {}"],
              "wholesaler": ["{} Beverages", "{} Drinks Wholesale"]}

# freshness incidents
CARRIER_OUTAGE = [date(2026, 5, 12), date(2026, 5, 13), date(2026, 5, 14)]   # no carrier file at all; backfilled on 05-15
BRNO_OUTAGE = (date(2026, 8, 6), date(2026, 8, 26))   # Moravia Express stops sending events for Brno shipments
LATE_FILES = {"erp_orders": 3, "wms_shipments": 2, "carrier_tracking": 7, "master_data/customers": 1}

ts = lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S")
sap_date = lambda d: d.strftime("%Y%m%d")


def season(d: date) -> float:
    """Demand multiplier: 1.0 in spring, ~1.45 in mid-July."""
    return 1 + .45 * np.exp(-(((d - date(2026, 7, 15)).days) / 32) ** 2)


def build_master(rng):
    customers = pd.DataFrame({"customer_id": range(100001, 100401)})
    customers["customer_type"] = rng.choice(list(TYPE_SHARE), size=400, p=list(TYPE_SHARE.values()))
    customers["dc_code"] = rng.choice(list(DCS), size=400, p=DC_SHARE)
    customers["city"] = customers.dc_code.map(DCS)
    customers["customer_name"] = [rng.choice(NAME_STYLE[t]).format(rng.choice(SURNAMES)) for t in customers.customer_type]
    onboard = [START] * 360 + sorted(START + timedelta(days=int(x)) for x in rng.integers(14, 168, 40))
    customers["onboarded_on"] = onboard
    customers["orders_from"] = [d if d == START else d + timedelta(days=1) for d in onboard]

    products = pd.DataFrame([
        {"sku": f"{code}-{pack}", "sku_name": f"{name}, {desc}", "brand": name, "brewery": BREWERIES[b],
         "pack": pack, "liters_per_pack": liters, "brand_weight": w,
         "launched_on": SUMMER_WHEAT_LAUNCH if code == "SW" else START}
        for code, name, b, w in BRANDS for pack, (desc, liters) in PACKS.items()])
    products["orders_from"] = [d if d == START else d + timedelta(days=1) for d in products.launched_on]
    return customers, products


def simulate(rng, customers, products):
    """The physical truth: orders, picks and carrier events before any extract goes wrong."""
    order_lines, wms, events, shipments = [], [], [], []
    n = 0
    for d in DAYS:
        active = customers[customers.orders_from <= d]
        p = active.customer_type.map(ORDER_RATE).to_numpy() * WEEKDAY[d.weekday()] * season(d)
        skus = products[products.orders_from <= d]
        for c in active[rng.random(len(active)) < p].itertuples():
            n += 1
            order_id, shipment_id = 50_000_000 + n, f"SH{n:07d}"
            w = skus.brand_weight * skus.pack.map(PACK_PREF[c.customer_type]).fillna(0)
            k = min(int(rng.integers(*LINES[c.customer_type])), int((w > 0).sum()))
            chosen = rng.choice(skus.sku.to_numpy(), size=k, replace=False, p=(w / w.sum()).to_numpy())
            promised = d + timedelta(days=LEAD_DAYS[c.customer_type])
            if promised.weekday() == 6:
                promised += timedelta(days=1)          # no deliveries on Sunday
            ship_date = promised + timedelta(days=int(rng.random() < DC_DELAY_PROB))
            shipped_at = datetime.combine(ship_date, time(5)) + timedelta(minutes=int(rng.integers(0, 240)))
            carrier = rng.choice(list(CARRIER_MIX[c.dc_code]), p=list(CARRIER_MIX[c.dc_code].values()))
            total_shipped = 0
            for i, sku in enumerate(chosen, start=1):
                qty = int(rng.integers(*QTY[c.customer_type]))
                order_lines.append((order_id, i * 10, d, c.customer_id, c.dc_code, promised, sku, qty))
                short_prob = .15 if sku.endswith("CAN24") and ship_date.month == 7 else .03   # July can shortage
                shipped = max(1, int(qty * rng.uniform(.5, .9))) if rng.random() < short_prob else qty
                total_shipped += shipped
                if ship_date <= END:
                    wms.append((shipment_id, order_id, i * 10, c.dc_code, sku, shipped, carrier, shipped_at))
            if ship_date > END:
                continue
            delay = int(rng.integers(1, 4)) if rng.random() < LATE_PROB[carrier] else 0
            delivered_at = (datetime.combine(ship_date + timedelta(days=delay), time(10))
                            + timedelta(minutes=int(rng.integers(0, 480))))
            delivered_qty = max(0, total_shipped - (int(rng.integers(1, 3)) if rng.random() < DAMAGE_PROB else 0))
            shipments.append((shipment_id, c.dc_code, carrier, promised, shipped_at, delivered_at))
            events.append((shipment_id, carrier, c.dc_code, "PICKED_UP", shipped_at + timedelta(minutes=30), None, shipped_at))
            for k_day in range(1, delay + 1):
                at = datetime.combine(ship_date + timedelta(days=k_day), time(7)) + timedelta(minutes=int(rng.integers(0, 60)))
                events.append((shipment_id, carrier, c.dc_code, "IN_TRANSIT", at, None, shipped_at))
            events.append((shipment_id, carrier, c.dc_code, "DELIVERED", delivered_at, delivered_qty, shipped_at))

    orders = pd.DataFrame(order_lines, columns=["order_id", "line", "order_date", "customer_id", "dc_code",
                                                "promised", "sku", "qty"])
    wms = pd.DataFrame(wms, columns=["shipment_id", "order_id", "line", "dc_code", "sku", "shipped_qty",
                                     "carrier_id", "shipped_at"])
    events = pd.DataFrame(events, columns=["shipment_id", "carrier_id", "dc_code", "status", "event_at",
                                           "delivered_qty", "shipped_at"])
    events = events[events.event_at.dt.date <= END].sort_values("event_at", kind="stable").reset_index(drop=True)
    events.insert(0, "event_id", [f"EV{i:08d}" for i in range(1, len(events) + 1)])
    shipments = pd.DataFrame(shipments, columns=["shipment_id", "dc_code", "carrier_id", "promised", "shipped_at",
                                                 "delivered_at"])
    return orders, wms, events, shipments


def extract_times(rng, days, n_late, late_from=None):
    """extracted_at per file: normally 01:00-03:00 the next morning, a few files after the 06:00 SLA.

    extracted_at travels as a column, so a header-only file cannot show it: late files are picked from late_from
    (the days that have rows) when given.
    """
    pool = late_from if late_from is not None else days
    late = set(rng.choice(pool, size=n_late, replace=False).tolist()) if n_late else set()
    out = {}
    for d in days:
        base = datetime.combine(d + timedelta(days=1), time(1))
        out[d] = (base + timedelta(hours=int(rng.integers(10, 21)), minutes=int(rng.integers(0, 60)))
                  if d in late else base + timedelta(minutes=int(rng.integers(0, 120))))
    return out, late


class AnswerKey:
    def __init__(self):
        self.rows = []

    def add(self, source, file_date, record_id, defect_type, dimension, reason):
        self.rows.append((source, str(file_date), record_id, defect_type, dimension, reason))

    def frame(self):
        return pd.DataFrame(self.rows, columns=["source", "file_date", "record_id", "defect_type", "dimension",
                                                "defect_reason"])


def pick(rng, keys, rate, taken):
    """Sample about rate * len(keys) keys not already carrying a defect (one defect per record)."""
    free = [k for k in keys if k not in taken]
    chosen = rng.choice(np.array(free, dtype=object), size=max(1, round(len(keys) * rate)), replace=False).tolist()
    taken.update(chosen)
    return chosen


def erp_extract(rng, orders, key):
    erp = pd.DataFrame({
        "VBELN": orders.order_id.map("{:010d}".format), "POSNR": orders.line.map("{:06d}".format),
        "ERDAT": orders.order_date.map(sap_date), "KUNNR": orders.customer_id.map("{:010d}".format),
        "MATNR": orders.sku, "KWMENG": orders.qty.map("{}.000".format), "VDATU": orders.promised.map(sap_date),
        "WERKS": orders.dc_code, "file_date": orders.order_date})
    rid = erp.VBELN + "/" + erp.POSNR
    taken, by_order = set(), erp.groupby("VBELN").groups

    def plant_orders(rate, defect, dimension, reason, mutate):
        for vbeln in pick(rng, list(by_order), rate, taken):
            idx = by_order[vbeln]
            mutate(idx)
            for i in idx:
                key.add("erp_orders", erp.at[i, "file_date"], rid[i], defect, dimension, reason)

    def set_col(col, value_fn):
        def mutate(idx):
            erp.loc[idx, col] = value_fn(idx)
        return mutate

    plant_orders(.003, "missing_customer_id", "completeness", "KUNNR is empty", set_col("KUNNR", lambda idx: ""))
    plant_orders(.004, "missing_promised_date", "completeness", "VDATU is empty or SAP null date 00000000",
                 set_col("VDATU", lambda idx: rng.choice(["00000000", ""])))
    plant_orders(.002, "unknown_customer", "validity", "KUNNR not in customer master",
                 set_col("KUNNR", lambda idx: f"{199000 + int(rng.integers(1, 999)):010d}"))
    plant_orders(.002, "bad_dc_code", "validity", "WERKS is not a known DC",
                 set_col("WERKS", lambda idx: rng.choice(["CZ9", "CZ07", "XX01"])))
    plant_orders(.0015, "invalid_date", "validity", "VDATU is not a calendar date",
                 set_col("VDATU", lambda idx: rng.choice(["20260231", "20260431", "20261301"])))
    plant_orders(.0015, "promised_before_ordered", "validity", "VDATU is earlier than ERDAT",
                 set_col("VDATU", lambda idx: sap_date(erp.at[idx[0], "file_date"] - timedelta(days=int(rng.integers(1, 4))))))

    taken_lines = set(i for v in taken for i in by_order[v])
    for i in pick(rng, list(erp.index), .003, taken_lines):
        q = int(orders.at[i, "qty"])
        erp.at[i, "KWMENG"] = rng.choice(["0.000", f"{q}.000-"])   # SAP writes negatives with a trailing minus
        key.add("erp_orders", erp.at[i, "file_date"], rid[i], "nonpositive_qty", "validity", "KWMENG is zero or negative")
    for i in pick(rng, list(erp.index), .002, taken_lines):
        erp.at[i, "MATNR"] = "XX-" + erp.at[i, "MATNR"].split("-")[1]
        key.add("erp_orders", erp.at[i, "file_date"], rid[i], "unknown_sku", "validity", "MATNR not in product master")
    return erp


def wms_extract(rng, wms, key):
    out = pd.DataFrame({
        "shipment_id": wms.shipment_id, "order_id": wms.order_id.astype(str), "order_line": wms.line,
        "dc_code": wms.dc_code, "sku": wms.sku, "shipped_qty": wms.shipped_qty.astype(str),
        "carrier_id": wms.carrier_id, "shipped_at": wms.shipped_at.map(ts), "file_date": wms.shipped_at.dt.date})
    messy = rng.random(len(out)) < .05                       # hand-typed DC codes: standardise, don't flag
    out.loc[messy, "dc_code"] = " " + out.loc[messy, "dc_code"].str.lower()
    rid = out.shipment_id + "/" + out.order_line.astype(str)
    taken = set()
    for i in pick(rng, list(out.index), .002, taken):
        out.at[i, "shipped_qty"] = rng.choice(["0", f"-{wms.at[i, 'shipped_qty']}"])
        key.add("wms_shipments", out.at[i, "file_date"], rid[i], "nonpositive_qty", "validity", "shipped_qty is zero or negative")
    for i in pick(rng, list(out.index), .001, taken):
        out.at[i, "dc_code"] = rng.choice(["CZ9", "CZ07", "XX01"])
        key.add("wms_shipments", out.at[i, "file_date"], rid[i], "bad_dc_code", "validity", "dc_code is not a known DC")
    for i in pick(rng, list(out.index), .002, taken):
        out.at[i, "carrier_id"] = ""
        key.add("wms_shipments", out.at[i, "file_date"], rid[i], "missing_carrier_id", "completeness", "carrier_id is empty")
    return out


def carrier_extract(rng, events, key):
    ev = events.copy()
    ev["file_date"] = ev.event_at.dt.date
    ev.loc[ev.file_date.isin(CARRIER_OUTAGE), "file_date"] = CARRIER_OUTAGE[-1] + timedelta(days=1)
    brno = ((ev.carrier_id == "CR02") & (ev.dc_code == "CZ02")
            & ev.file_date.between(*BRNO_OUTAGE))
    ev.loc[brno, "file_date"] = BRNO_OUTAGE[1] + timedelta(days=1)
    backfilled = ev.file_date != ev.event_at.dt.date
    for i in ev.index[backfilled]:
        key.add("carrier_tracking", ev.at[i, "file_date"], ev.at[i, "event_id"], "late_arriving_record", "freshness",
                "event sent days after it happened (feed outage backfill)")

    days = [d for d in DAYS if d not in CARRIER_OUTAGE]
    extracted, late = extract_times(rng, days, LATE_FILES["carrier_tracking"])
    for d in CARRIER_OUTAGE:
        key.add("carrier_tracking", d, "", "missing_file", "freshness", "no carrier file received for this day")
    for d in sorted(late):
        key.add("carrier_tracking", d, "", "late_file", "freshness", "file extracted after the 06:00 SLA")
    ev["extracted_at"] = ev.file_date.map(extracted)

    delivered = list(ev.index[(ev.status == "DELIVERED") & ~backfilled])
    taken = set()
    for i in pick(rng, delivered, .006, taken):
        ev.at[i, "delivered_qty"] = np.nan
        key.add("carrier_tracking", ev.at[i, "file_date"], ev.at[i, "event_id"], "missing_delivered_qty", "completeness",
                "DELIVERED event without delivered_qty")
    for i in pick(rng, delivered, .003, taken):     # carrier clock bug: wrong time, still sent in the same file
        ev.at[i, "event_at"] = ev.at[i, "shipped_at"] - timedelta(minutes=int(rng.integers(60, 1800)))
        key.add("carrier_tracking", ev.at[i, "file_date"], ev.at[i, "event_id"], "delivered_before_shipped", "validity",
                "delivered before the WMS shipped it")
    for i in pick(rng, delivered, .001, taken):
        ev.at[i, "event_at"] = ev.at[i, "extracted_at"] + timedelta(days=int(rng.integers(1, 5)))
        key.add("carrier_tracking", ev.at[i, "file_date"], ev.at[i, "event_id"], "event_after_extraction", "validity",
                "event timestamp is later than the file was extracted")

    status = ev.status.where(ev.carrier_id != "CR04", ev.status.str.lower())   # Silesia sends lowercase statuses
    out = pd.DataFrame({
        "event_id": ev.event_id, "shipment_id": ev.shipment_id, "carrier_id": ev.carrier_id, "status": status,
        "event_at": ev.event_at.map(ts), "delivered_qty": ev.delivered_qty.map(lambda q: "" if pd.isna(q) else str(int(q))),
        "extracted_at": ev.extracted_at.map(ts), "file_date": ev.file_date})
    return out, days, extracted


def master_extract(rng, customers, products, key):
    """Customer and product rows per file date: full load on day 1, onboarding and changes after."""
    cust = customers[["customer_id", "customer_name", "customer_type", "dc_code", "city"]].copy()
    cust["file_date"] = customers.onboarded_on
    initial = list(cust.index[cust.file_date == START])
    taken = set()
    for i in pick(rng, initial, 4 / 360, taken):
        cust.at[i, "dc_code"] = ""
        key.add("master_data", START, f"customers/{cust.at[i, 'customer_id']}", "missing_dc_code", "completeness",
                "customer has no dc_code")
    for i in pick(rng, initial, 3 / 360, taken):
        cust.at[i, "customer_type"] = "UNKNOWN"
        key.add("master_data", START, f"customers/{cust.at[i, 'customer_id']}", "invalid_customer_type", "validity",
                "customer_type is not bar, retailer or wholesaler")

    extra = []
    for n, i in enumerate(pick(rng, initial, 6 / 360, taken)):   # 3 exact repeats, 3 with a different DC
        row = cust.loc[i].copy()
        if n >= 3:
            row["dc_code"] = rng.choice([d for d in DCS if d != row.dc_code])
        extra.append(row)
        key.add("master_data", START, f"customers/{row.customer_id}", "duplicate_key", "validity",
                "customer_id appears twice in one file" + (" with conflicting dc_code" if n >= 3 else ""))
    onboarded = list(cust.index[cust.file_date > START])
    for i in pick(rng, onboarded, 2 / 40, set()):
        row = cust.loc[i].copy()
        row["customer_type"] = rng.choice([t for t in TYPE_SHARE if t != row.customer_type])
        extra.append(row)
        key.add("master_data", row.file_date, f"customers/{row.customer_id}", "duplicate_key", "validity",
                "customer_id appears twice in one file with conflicting customer_type")
    for i in pick(rng, initial, 8 / 360, taken):              # legitimate renames in later deltas: not defects
        row = cust.loc[i].copy()
        row["customer_name"] += " & Sons"
        row["file_date"] = date(2026, 4, 1) + timedelta(days=int(rng.integers(0, 140)))
        extra.append(row)
    cust = pd.concat([cust, pd.DataFrame(extra)], ignore_index=True).sort_values(["file_date", "customer_id"], kind="stable")
    cust["valid_from"] = cust.file_date.map(str)

    prod = products[["sku", "sku_name", "brand", "brewery", "pack", "liters_per_pack", "launched_on"]].copy()
    prod["file_date"] = products.launched_on
    dup = prod[prod.sku == "TP-CAN24"]
    prod = pd.concat([prod, dup], ignore_index=True).sort_values(["file_date", "sku"], kind="stable")
    key.add("master_data", START, "products/TP-CAN24", "duplicate_key", "validity", "sku appears twice in one file")

    dcs = pd.DataFrame({"dc_code": list(DCS), "dc_name": [f"DC {c}" for c in DCS.values()], "city": list(DCS.values()),
                        "file_date": START})
    carriers = pd.DataFrame({"carrier_id": list(CARRIERS), "carrier_name": list(CARRIERS.values()), "file_date": START})
    return {"customers": cust, "products": prod, "dcs": dcs, "carriers": carriers}


def write_daily(df, folder, days, extracted):
    """One CSV per day, header-only when nothing happened that day (an empty file still proves the feed is alive)."""
    folder.mkdir(parents=True, exist_ok=True)
    cols = [c for c in df.columns if c not in ("file_date", "extracted_at")] + ["extracted_at"]
    groups = {d: g for d, g in df.groupby("file_date")}
    for d in days:
        part = groups.get(d, df.iloc[0:0]).copy()
        part["extracted_at"] = ts(extracted[d])
        part[cols].to_csv(folder / f"{d}.csv", index=False)
    return len(days)


def main(raw_dir=RAW):
    rng = np.random.default_rng(SEED)
    shutil.rmtree(raw_dir, ignore_errors=True)
    key = AnswerKey()
    customers, products = build_master(rng)
    orders, wms, events, shipments = simulate(rng, customers, products)

    files = {}
    erp = erp_extract(rng, orders, key)
    extracted, late = extract_times(rng, DAYS, LATE_FILES["erp_orders"])
    files["erp_orders"] = (write_daily(erp, raw_dir / "erp_orders", DAYS, extracted), len(erp))
    for d in sorted(late):
        key.add("erp_orders", d, "", "late_file", "freshness", "file extracted after the 06:00 SLA")

    w = wms_extract(rng, wms, key)
    extracted, late = extract_times(rng, DAYS, LATE_FILES["wms_shipments"])
    files["wms_shipments"] = (write_daily(w, raw_dir / "wms_shipments", DAYS, extracted), len(w))
    for d in sorted(late):
        key.add("wms_shipments", d, "", "late_file", "freshness", "file extracted after the 06:00 SLA")

    car, car_days, extracted = carrier_extract(rng, events, key)
    files["carrier_tracking"] = (write_daily(car.drop(columns="extracted_at"), raw_dir / "carrier_tracking", car_days, extracted), len(car))

    n_files = n_rows = 0
    for entity, df in master_extract(rng, customers, products, key).items():
        extracted, late = extract_times(rng, DAYS, LATE_FILES.get(f"master_data/{entity}", 0),
                                        late_from=sorted(set(df.file_date)))
        n_files += write_daily(df, raw_dir / "master_data" / entity, DAYS, extracted)
        n_rows += len(df)
        for d in sorted(late):
            key.add("master_data", d, entity, "late_file", "freshness", "file extracted after the 06:00 SLA")
    files["master_data"] = (n_files, n_rows)

    answers = key.frame().sort_values(["source", "file_date", "defect_type", "record_id"], kind="stable")
    answers.to_csv(raw_dir / "_planted_defects.csv", index=False)

    print(f"{orders.order_id.nunique():,} orders, {len(orders):,} order lines, {len(shipments):,} shipments\n")
    print(pd.DataFrame(files, index=["files", "rows"]).T.to_string(), "\n")
    print(answers.groupby(["source", "defect_type", "dimension"]).size().rename("planted").to_string(), "\n")
    s = shipments.assign(late=shipments.delivered_at.dt.date > shipments.promised)
    s = s[s.delivered_at.dt.date <= END]
    print(f"late deliveries: {s.late.sum():,} of {len(s):,} ({s.late.mean():.1%}); "
          f"TransBohemia's share of late: {(s[s.late].carrier_id == 'CR03').mean():.1%}")


if __name__ == "__main__":
    main()
