#!/usr/bin/env python3
"""
ECE-023 Domestic/Commercial Electricity Billing Engine (slab tariff + PF penalty)
Single-file version - CORRECTED. Reads commands.txt + the three CSV masters and
writes bills.csv and collection_summary.csv in the exact evaluation format.

Usage:  python billing_engine.py <data_dir> [out_dir]
        (data_dir holds commands.txt and the CSVs; out_dir defaults to ".")

Business rules (brief BR-01..BR-08 + pack conventions):
 BR-01 Domestic telescopic slabs : 50 @4.75, 51-100 @7.00, 101-200 @8.25, >200 @9.50
 BR-02 Commercial slabs          : 100 @9.00, >100 @10.50
 BR-03 Fixed charge              : Rs110/kW domestic, Rs160/kW commercial, every month
 BR-04 PF penalty (COMMERCIAL)   : 1% of energy per WHOLE 0.01 below 0.90, cap 15%
 BR-05 Tax                       : 9% of (energy + fixed + PF penalty); interest not taxed
 BR-06 Rollover                  : closing < opening -> (99999-opening)+closing+1
 BR-07 Late payment              : due = bill date+15; payment ON due date is on time;
                                   interest = 1% x BILL TOTAL x ceil(days late/30), placed on the
                                   consumer's first bill dated AFTER the payment date; not taxed
 BR-08 Rounding                  : line items 2dp half-up; total to whole rupee; difference shown
All money is Decimal (no binary floating point).
"""
import csv
import math
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP

# ===================================================================== tariff
# (band width in units, Rs per unit); None = unlimited. Telescopic: each band is
# priced at its own rate.
DOMESTIC_SLABS = [(50, Decimal("4.75")), (50, Decimal("7.00")), (100, Decimal("8.25")), (None, Decimal("9.50"))]
COMMERCIAL_SLABS = [(100, Decimal("9.00")), (None, Decimal("10.50"))]
FIXED_CHARGE_RATE = {"DOMESTIC": Decimal("110"), "COMMERCIAL": Decimal("160")}   # Rs per kW
TAX_RATE = Decimal("0.09")
PF_THRESHOLD = Decimal("0.90")
PF_PENALTY_STEP = Decimal("0.01")
PF_PENALTY_PER_STEP = Decimal("0.01")
PF_PENALTY_CAP = Decimal("0.15")
DUE_DAYS = 15
INTEREST_RATE_PER_PERIOD = Decimal("0.01")
LATE_PERIOD_DAYS = 30
METER_MAX = 99999

DATE_FMT = "%Y-%m-%d"
CATEGORIES = ("DOMESTIC", "COMMERCIAL")


def round2(x):
    """Half-up to 2 decimals (Decimal)."""
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def round_rupee(x):
    """Half-up to a whole rupee (Decimal)."""
    return Decimal(x).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def parse_date(s):
    return datetime.strptime(s.strip(), DATE_FMT)


def fmt5(n):
    return f"{int(n):05d}"


def energy_charge(units, slabs):
    """Telescopic slab charge, each band rounded to 2dp, summed."""
    remaining, charge = units, Decimal("0.00")
    for width, rate in slabs:
        if remaining <= 0:
            break
        take = remaining if width is None else min(remaining, width)
        charge += round2(take * rate)
        remaining -= take
    return round2(charge)


def pf_penalty(category, energy, avg_pf_str):
    """BR-04. Commercial only; whole 0.01 steps below 0.90 (floor); cap 15%."""
    if category != "COMMERCIAL" or (avg_pf_str or "").strip().upper() in ("", "NONE"):
        return Decimal("0.00")
    avg_pf = Decimal(avg_pf_str.strip())
    if avg_pf >= PF_THRESHOLD:
        return Decimal("0.00")
    steps = int(((PF_THRESHOLD - avg_pf) / PF_PENALTY_STEP).to_integral_value(rounding=ROUND_FLOOR))
    pct = min(steps * PF_PENALTY_PER_STEP, PF_PENALTY_CAP)
    return round2(energy * pct)


class Engine:
    def __init__(self):
        self.consumers = {}                       # rr -> row (file order kept)
        self.readings = defaultdict(list)         # rr -> readings sorted by date
        self.payments = []                        # payment rows (file order)
        self.bills = {}                           # (rr, month) -> bill dict
        self._charged = set()                     # payment_ids whose interest is already on a bill

    # ------------------------------------------------------------ loading
    @staticmethod
    def _rows(path):
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                yield {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}

    def load_consumers(self, path):
        for row in self._rows(path):
            self.consumers[row["rr_number"]] = row

    def load_readings(self, path):
        for row in self._rows(path):
            self.readings[row["rr_number"]].append(row)
        for rr in self.readings:
            self.readings[rr].sort(key=lambda r: r["reading_date"])

    def load_payments(self, path):
        for row in self._rows(path):
            self.payments.append(row)

    # ------------------------------------------------------------ billing
    def generate_bills(self, bill_month):
        """One bill per consumer whose reading falls in bill_month (run months in order)."""
        for rr, consumer in sorted(self.consumers.items()):
            idx = next((i for i, r in enumerate(self.readings[rr]) if r["reading_date"][:7] == bill_month), None)
            if idx is None or (rr, bill_month) in self.bills:
                continue
            reading = self.readings[rr][idx]
            category = consumer["category"].upper()

            opening = int(consumer["meter_start_reading"]) if idx == 0 else int(self.readings[rr][idx - 1]["closing_reading"])
            closing = int(reading["closing_reading"])
            units = closing - opening if closing >= opening else (METER_MAX - opening) + closing + 1   # BR-06

            energy = energy_charge(units, DOMESTIC_SLABS if category == "DOMESTIC" else COMMERCIAL_SLABS)
            fixed = round2(FIXED_CHARGE_RATE[category] * Decimal(consumer["sanctioned_load_kw"]))
            penalty = pf_penalty(category, energy, reading["avg_pf"])
            tax = round2((energy + fixed + penalty) * TAX_RATE)

            bill_date = reading["reading_date"]
            bill = {
                "bill_id": f"BL-{bill_month.replace('-', '')}-{rr}", "rr_number": rr, "category": category,
                "bill_month": bill_month, "bill_date": bill_date,
                "due_date": (parse_date(bill_date) + timedelta(days=DUE_DAYS)).strftime(DATE_FMT),
                "opening_reading": fmt5(opening), "closing_reading": fmt5(closing), "units": units,
                "energy_charge_rs": energy, "fixed_charge_rs": fixed, "pf_penalty_rs": penalty, "tax_rs": tax,
                "late_interest_rs": self._interest_for_new_bill(rr, bill_date),
            }
            subtotal = energy + fixed + penalty + tax + bill["late_interest_rs"]
            bill["total_rs"] = round_rupee(subtotal)
            bill["rounding_rs"] = round2(bill["total_rs"] - subtotal)
            self.bills[(rr, bill_month)] = bill

    def _interest_for_new_bill(self, rr, bill_date):
        """Sum interest of this consumer's late payments that fall before `bill_date` and
        have not yet been charged. The interest base is the paid bill's FINAL total
        (including any interest it carried) - bills are created in date order, so that
        total is already final."""
        total = Decimal("0.00")
        for pay in self.payments:
            if pay["rr_number"] != rr or pay["payment_id"] in self._charged:
                continue
            paid_bill = self.bills.get((rr, pay["bill_month"]))
            if paid_bill is None:
                continue
            pay_date, due = parse_date(pay["payment_date"]), parse_date(paid_bill["due_date"])
            if pay_date <= due or pay_date >= parse_date(bill_date):    # on time / not before this bill
                continue
            periods = math.ceil((pay_date - due).days / LATE_PERIOD_DAYS)
            total += round2(INTEREST_RATE_PER_PERIOD * paid_bill["total_rs"] * periods)
            self._charged.add(pay["payment_id"])
        return round2(total)

    # ------------------------------------------------------------ summary
    def collection_summary(self, bill_month):
        rows = []
        for category in CATEGORIES:
            bills = [b for (r, m), b in sorted(self.bills.items()) if m == bill_month and b["category"] == category]
            keys = {(b["rr_number"], bill_month) for b in bills}
            pays = [p for p in self.payments if (p["rr_number"], p["bill_month"]) in keys]
            billed = sum((b["total_rs"] for b in bills), Decimal("0"))
            collected = sum((Decimal(p["amount_rs"]) for p in pays), Decimal("0"))
            late = sum(1 for p in pays
                       if parse_date(p["payment_date"]) > parse_date(self.bills[(p["rr_number"], bill_month)]["due_date"]))
            rows.append([bill_month, category, len(bills), sum(b["units"] for b in bills),
                         round2(billed), round2(collected), round2(billed - collected), late,
                         round2(sum((b["late_interest_rs"] for b in bills), Decimal("0")))])
        return rows

    # ------------------------------------------------------------ output
    def write_bills_csv(self, path):
        cols = ["bill_id", "rr_number", "category", "bill_month", "bill_date", "due_date", "opening_reading",
                "closing_reading", "units", "energy_charge_rs", "fixed_charge_rs", "pf_penalty_rs", "tax_rs",
                "late_interest_rs", "rounding_rs", "total_rs"]
        with open(path, "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(cols)
            for b in sorted(self.bills.values(), key=lambda b: (b["bill_month"], b["rr_number"])):
                w.writerow([b[c] if c in ("bill_id", "rr_number", "category", "bill_month", "bill_date", "due_date",
                                          "opening_reading", "closing_reading", "units") else f"{b[c]:.2f}"
                            for c in cols])

    def write_summary_csv(self, path, months):
        cols = ["bill_month", "category", "bills", "units", "billed_rs", "collected_rs", "outstanding_rs",
                "late_payments", "interest_billed_rs"]
        with open(path, "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(cols)
            for m in sorted(set(months)):
                for r in self.collection_summary(m):
                    w.writerow([x if i in (0, 1, 2, 3, 7) else f"{x:.2f}" for i, x in enumerate(r)])


def run_commands(commands_path, data_dir="."):
    engine, summary_months = Engine(), []
    with open(commands_path, encoding="utf-8-sig") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            cmd = parts[0].upper()
            if cmd == "LOAD_CONSUMERS":
                engine.load_consumers(f"{data_dir}/{parts[1]}")
            elif cmd == "LOAD_READINGS":
                engine.load_readings(f"{data_dir}/{parts[1]}")
            elif cmd == "LOAD_PAYMENTS":
                engine.load_payments(f"{data_dir}/{parts[1]}")
            elif cmd == "GENERATE_BILLS":
                engine.generate_bills(parts[1])
            elif cmd == "COLLECTION_SUMMARY":
                summary_months.append(parts[1])
            else:
                raise ValueError(f"commands.txt line {n}: unknown command {cmd}")
    return engine, summary_months


if __name__ == "__main__":
    import os
    import sys
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    os.makedirs(out_dir, exist_ok=True)
    eng, months = run_commands(f"{data_dir}/commands.txt", data_dir)
    eng.write_bills_csv(f"{out_dir}/bills.csv")
    eng.write_summary_csv(f"{out_dir}/collection_summary.csv", months)
    print(f"Wrote {len(eng.bills)} bills across {len(set(months))} summary month(s) to {out_dir}/")
