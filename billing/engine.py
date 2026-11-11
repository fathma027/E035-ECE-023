"""BillingEngine - the stateful core: consumers, readings, bills, payments."""
import csv
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List, Tuple

from . import config as cfg
from .interest import interest_for_payment, periods_overdue
from .models import Bill, Consumer, Payment, Reading
from .money import q2, round_rupee
from .tariff import (electricity_tax, energy_charge, fixed_charge, pf_penalty,
                     units_consumed)
from . import validation as v
from .validation import ValidationError


class BillingEngine:
    def __init__(self):
        self.consumers: Dict[str, Consumer] = {}
        self.readings: Dict[Tuple[str, str], Reading] = {}
        self.bills: Dict[Tuple[str, str], Bill] = {}
        self.pending_payments: List[Payment] = []
        self._payment_ids = set()
        self._interest_charged = set()                   # payment ids whose interest is already on a bill
        self._auto_id = 0
        self.diagnostics: List[Tuple[str, str]] = []     # (level, message)

    # ------------------------------------------------------------ diagnostics
    def diag(self, level: str, message: str):
        self.diagnostics.append((level, message))

    # ------------------------------------------------------------ FR-1 register
    def register_consumer(self, rr, category, load, start) -> Consumer:
        rr = v.parse_rr(rr)
        category = v.parse_category(category)
        load_kw = v.parse_load(load)
        start_reading = v.parse_meter(start, "meter start reading", "VR-04")
        if rr in self.consumers:
            raise ValidationError("VR-06", f"RR number {rr} is already registered")
        c = Consumer(rr, category, load_kw, start_reading)
        self.consumers[rr] = c
        return c

    # ------------------------------------------------------------ FR-2 readings
    def add_reading(self, rr, reading_date, closing, pf) -> Reading:
        rr = v.parse_rr(rr)
        if rr not in self.consumers:
            raise ValidationError("VR-13", f"RR number {rr} is not registered")
        c = self.consumers[rr]
        d = v.parse_date(reading_date, "reading date", "VR-05")
        closing_i = v.parse_meter(closing, "closing reading", "VR-07")
        pf_d = v.parse_pf(pf, c.category)
        r = Reading(rr, d, closing_i, pf_d)
        if (rr, r.month) in self.readings:
            raise ValidationError("VR-14", f"duplicate reading for {rr} in {r.month}")
        self.readings[(rr, r.month)] = r
        return r

    # ------------------------------------------------------------ FR-3 billing
    def generate_bills(self, month: str) -> List[Bill]:
        month = v.parse_month(month)
        made: List[Bill] = []
        for rr in sorted(self.consumers):
            reading = self.readings.get((rr, month))
            if reading is None:
                self.diag("WARN", f"{rr}: no reading for {month}; no bill generated")
                continue
            if (rr, month) in self.bills:
                self.diag("WARN", f"{rr}: {month} already billed; skipped")
                continue
            try:
                made.append(self._bill_one(self.consumers[rr], reading))
            except ValidationError as e:
                self.diag("ERROR", f"{rr} {month}: {e}")
        self._apply_pending()
        return made

    def _bill_one(self, c: Consumer, r: Reading) -> Bill:
        if c.last_billed_month and r.month <= c.last_billed_month:
            raise ValidationError("VR-15", f"month is not after last billed month {c.last_billed_month}")
        if c.last_reading_date and r.reading_date <= c.last_reading_date:
            raise ValidationError("VR-16", f"reading date {r.reading_date} is not after previous reading date {c.last_reading_date}")
        if c.last_billed_month:
            gap = (int(r.month[:4]) * 12 + int(r.month[5:])) - (int(c.last_billed_month[:4]) * 12 + int(c.last_billed_month[5:]))
            if gap > 1:
                self.diag("WARN", f"{c.rr}: {gap - 1} month(s) without a reading before {r.month}; consumption billed as one month")

        units, rollover = units_consumed(c.last_closing, r.closing)
        energy, slabs = energy_charge(c.category, units)
        fixed = fixed_charge(c.category, c.load_kw)
        penalty, pct = pf_penalty(c.category, energy, r.pf)
        tax = electricity_tax(energy, fixed, penalty)

        # BR-07: interest for late payments of earlier bills, charged on the first
        # bill dated strictly AFTER the payment date.
        interest_detail, newly_charged = [], []
        for (rr2, m2) in sorted(k for k in self.bills if k[0] == c.rr):
            prior = self.bills[(rr2, m2)]
            for p in sorted(prior.payments, key=lambda p: (p.pay_date, p.payment_id)):
                if p.payment_id in self._interest_charged or p.pay_date >= r.reading_date:
                    continue
                if periods_overdue(prior.due_date, p.pay_date) == 0:
                    continue
                interest_detail.append((p.payment_id, m2, interest_for_payment(prior, p)))
                newly_charged.append(p.payment_id)
        interest = q2(sum((a for _, _, a in interest_detail), Decimal("0")))

        # BR-08: line items to 2 dp, total to whole rupee, difference shown.
        gross = energy + fixed + penalty + tax + interest
        total = round_rupee(gross)
        rounding = q2(total - gross)

        bill = Bill(rr=c.rr, category=c.category, month=r.month, bill_date=r.reading_date,
                    due_date=r.reading_date + timedelta(days=cfg.DUE_DAYS), load_kw=c.load_kw,
                    opening=c.last_closing, closing=r.closing, units=units, rollover=rollover,
                    pf=r.pf, slabs=slabs, energy=energy, fixed=fixed, pf_pct=pct,
                    pf_penalty=penalty, tax=tax, interest=interest,
                    interest_detail=interest_detail, rounding=rounding, total=total)
        # Commit state only after everything succeeded.
        self._interest_charged.update(newly_charged)
        self.bills[(c.rr, r.month)] = bill
        c.last_closing, c.last_reading_date, c.last_billed_month = r.closing, r.reading_date, r.month
        return bill

    # ------------------------------------------------------------ FR-4 payments
    def record_payment(self, payment_id, rr, bill_month, pay_date, amount) -> Payment:
        rr = v.parse_rr(rr)
        if rr not in self.consumers:
            raise ValidationError("VR-13", f"RR number {rr} is not registered")
        month = v.parse_month(bill_month)
        d = v.parse_date(pay_date, "payment date", "VR-10")
        amt = v.parse_amount(amount)
        pid = (payment_id or "").strip()
        if not pid:
            self._auto_id += 1
            pid = f"AUTO{self._auto_id:05d}"
        if pid in self._payment_ids:
            raise ValidationError("VR-17", f"duplicate payment id {pid}")
        p = Payment(pid, rr, month, d, amt)
        bill = self.bills.get((rr, month))
        if bill is None:
            self._payment_ids.add(pid)
            self.pending_payments.append(p)       # bill not generated yet - retry later
            return p
        self._attach(bill, p)
        self._payment_ids.add(pid)
        return p

    def _attach(self, bill: Bill, p: Payment):
        if p.pay_date < bill.bill_date:
            raise ValidationError("VR-18", f"payment {p.payment_id} dated {p.pay_date} is before bill date {bill.bill_date}")
        if p.amount > bill.outstanding:
            raise ValidationError("VR-19", f"payment {p.payment_id} of {p.amount} exceeds outstanding {bill.outstanding} on {bill.bill_id}")
        if p.amount != bill.total:
            self.diag("WARN", f"payment {p.payment_id}: amount {p.amount} differs from bill total {bill.total} ({bill.bill_id}); recorded as received")
        bill.payments.append(p)

    def _apply_pending(self):
        still = []
        for p in self.pending_payments:
            bill = self.bills.get((p.rr, p.bill_month))
            if bill is None:
                still.append(p)
                continue
            try:
                self._attach(bill, p)
            except ValidationError as e:
                self._payment_ids.discard(p.payment_id)
                self.diag("ERROR", f"payment {p.payment_id}: {e}")
        self.pending_payments = still

    def apply_pending_payments(self):
        self._apply_pending()

    # ------------------------------------------------------------ FR-5 summary
    def collection_summary(self, month: str, asof=None):
        """Per-category totals for bills of `month`. collected = payments against
        those bills (any payment date unless `asof` is given); late_payments =
        bills of the month paid after their due date; interest = late-interest
        lines printed ON the month's bills."""
        month = v.parse_month(month)
        rows = {}
        for cat in cfg.CATEGORIES:
            rows[cat] = dict(bills=0, units=0, energy=Decimal("0.00"), fixed=Decimal("0.00"),
                             pf_penalty=Decimal("0.00"), tax=Decimal("0.00"), interest=Decimal("0.00"),
                             rounding=Decimal("0.00"), billed=Decimal("0.00"), collected=Decimal("0.00"),
                             outstanding=Decimal("0.00"), late_payments=0)
        for (rr, m), b in self.bills.items():
            if m != month:
                continue
            r = rows[b.category]
            pays = [p for p in b.payments if asof is None or p.pay_date <= asof]
            paid = sum((p.amount for p in pays), Decimal("0.00"))
            r["bills"] += 1
            r["units"] += b.units
            if any(p.pay_date > b.due_date for p in pays):
                r["late_payments"] += 1
            for k, val in (("energy", b.energy), ("fixed", b.fixed), ("pf_penalty", b.pf_penalty),
                           ("tax", b.tax), ("interest", b.interest), ("rounding", b.rounding),
                           ("billed", b.total), ("collected", paid), ("outstanding", b.total - paid)):
                r[k] += val
        return rows
