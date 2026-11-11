"""Evaluation output files: bills.csv and collection_summary.csv (column order fixed by the pack)."""
import csv
import os

from .config import CATEGORIES
from .money import fmt

BILL_COLS = ["bill_id", "rr_number", "category", "bill_month", "bill_date", "due_date", "opening_reading",
             "closing_reading", "units", "energy_charge_rs", "fixed_charge_rs", "pf_penalty_rs", "tax_rs",
             "late_interest_rs", "rounding_rs", "total_rs"]
SUMMARY_COLS = ["bill_month", "category", "bills", "units", "billed_rs", "collected_rs", "outstanding_rs",
                "late_payments", "interest_billed_rs"]


def bill_id(b) -> str:
    return f"BL-{b.month.replace('-', '')}-{b.rr}"


def write_bills_csv(path, bills):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(BILL_COLS)
        for b in sorted(bills, key=lambda b: (b.month, b.rr)):
            w.writerow([bill_id(b), b.rr, b.category, b.month, b.bill_date, b.due_date, f"{b.opening:05d}",
                        f"{b.closing:05d}", b.units, fmt(b.energy), fmt(b.fixed), fmt(b.pf_penalty), fmt(b.tax),
                        fmt(b.interest), fmt(b.rounding), fmt(b.total)])


def write_summary_csv(path, summaries):
    """summaries: {month: {category: row}}"""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(SUMMARY_COLS)
        for month in sorted(summaries):
            for cat in CATEGORIES:                       # DOMESTIC first
                r = summaries[month][cat]
                w.writerow([month, cat, r["bills"], r["units"], fmt(r["billed"]), fmt(r["collected"]),
                            fmt(r["outstanding"]), r["late_payments"], fmt(r["interest"])])
