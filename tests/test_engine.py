"""Engine-level tests: billing, ingestion rules, payments, interest, summary."""
import unittest
from datetime import date
from decimal import Decimal as D

from billing.engine import BillingEngine
from billing.validation import ValidationError


def engine_with(*consumers):
    e = BillingEngine()
    for c in consumers:
        e.register_consumer(*c)
    return e


def bill_one(e, rr, d, closing, pf="", month=None):
    e.add_reading(rr, d, closing, pf)
    month = month or d[:7]
    return [b for b in e.generate_bills(month) if b.rr == rr][0]


class TestBillLines(unittest.TestCase):
    def test_domestic_130_units_full_bill(self):
        e = engine_with(("RR1001", "DOMESTIC", "3", "120"))
        b = bill_one(e, "RR1001", "2026-07-28", "250")
        self.assertEqual((b.units, b.energy, b.fixed, b.pf_penalty, b.tax),
                         (130, D("835.00"), D("330.00"), D("0.00"), D("104.85")))
        self.assertEqual((b.rounding, b.total), (D("0.15"), D("1270")))
        self.assertEqual(b.due_date, date(2026, 8, 12))

    def test_commercial_pf_085(self):
        e = engine_with(("RR2001", "COMMERCIAL", "5", "1000"))
        b = bill_one(e, "RR2001", "2026-07-25", "1150", "0.85")
        self.assertEqual((b.energy, b.fixed, b.pf_penalty, b.tax), (D("1425.00"), D("800.00"), D("71.25"), D("206.66")))
        self.assertEqual((b.rounding, b.total), (D("0.09"), D("2503")))

    def test_commercial_pf_exactly_090(self):
        e = engine_with(("RR2001", "COMMERCIAL", "5", "1000"))
        b = bill_one(e, "RR2001", "2026-07-25", "1150", "0.90")
        self.assertEqual(b.pf_penalty, D("0.00"))

    def test_commercial_pf_070_cap(self):
        e = engine_with(("RR2001", "COMMERCIAL", "5", "1000"))
        b = bill_one(e, "RR2001", "2026-07-25", "1150", "0.70")
        self.assertEqual((b.pf_penalty, b.pf_pct), (D("213.75"), D("0.15")))
        # tax = (1425 + 800 + 213.75) * 9% = 219.4875 -> 219.49 ; gross = 2658.24 -> 2658
        self.assertEqual((b.tax, b.rounding, b.total), (D("219.49"), D("-0.24"), D("2658")))

    def test_zero_consumption_month(self):
        e = engine_with(("RR1002", "DOMESTIC", "2", "500"))
        b = bill_one(e, "RR1002", "2026-07-20", "500")
        self.assertEqual((b.units, b.energy, b.fixed, b.tax), (0, D("0.00"), D("220.00"), D("19.80")))
        self.assertEqual((b.rounding, b.total), (D("0.20"), D("240")))

    def test_zero_consumption_commercial_with_bad_pf(self):
        e = engine_with(("RR2002", "COMMERCIAL", "1", "10"))
        b = bill_one(e, "RR2002", "2026-07-20", "10", "0.60")
        self.assertEqual((b.energy, b.pf_penalty, b.fixed), (D("0.00"), D("0.00"), D("160.00")))

    def test_rollover_month_from_brief(self):
        e = engine_with(("RR1003", "DOMESTIC", "1", "99980"))
        b = bill_one(e, "RR1003", "2026-07-22", "00012")
        self.assertEqual((b.units, b.rollover, b.energy), (32, True, D("152.00")))

    def test_line_items_always_reconcile_to_total(self):
        e = engine_with(("RR1004", "DOMESTIC", "1.5", "0"), ("RR2003", "COMMERCIAL", "7.25", "0"))
        for units in (0, 1, 49, 50, 51, 99, 100, 101, 199, 200, 201, 999):
            e2 = engine_with(("RR1004", "DOMESTIC", "1.5", "0"), ("RR2003", "COMMERCIAL", "7.25", "0"))
            e2.add_reading("RR1004", "2026-07-20", str(units), "")
            e2.add_reading("RR2003", "2026-07-20", str(units), "0.82")
            for b in e2.generate_bills("2026-07"):
                self.assertEqual(b.energy + b.fixed + b.pf_penalty + b.tax + b.interest + b.rounding, b.total)
                self.assertEqual(b.total, b.total.to_integral_value())
                self.assertLessEqual(abs(b.rounding), D("0.50"))


class TestIngestion(unittest.TestCase):
    def setUp(self):
        self.e = engine_with(("RR1001", "DOMESTIC", "3", "100"), ("RR2001", "COMMERCIAL", "5", "100"))

    def rejects(self, code, *args):
        with self.assertRaises(ValidationError) as cm:
            self.e.add_reading(*args)
        self.assertEqual(cm.exception.code, code)

    def test_unknown_rr(self):            self.rejects("VR-13", "RR9999", "2026-07-20", "150", "")
    def test_bad_date(self):              self.rejects("VR-05", "RR1001", "2026-07-32", "150", "")
    def test_bad_closing(self):           self.rejects("VR-07", "RR1001", "2026-07-20", "123456", "")
    def test_commercial_needs_pf(self):   self.rejects("VR-08", "RR2001", "2026-07-20", "150", "")
    def test_pf_out_of_range(self):       self.rejects("VR-09", "RR2001", "2026-07-20", "150", "1.2")
    def test_duplicate_month(self):
        self.e.add_reading("RR1001", "2026-07-20", "150", "")
        self.rejects("VR-14", "RR1001", "2026-07-25", "160", "")

    def test_duplicate_registration(self):
        with self.assertRaises(ValidationError) as cm:
            self.e.register_consumer("rr1001", "DOMESTIC", "1", "0")
        self.assertEqual(cm.exception.code, "VR-06")

    def test_missing_reading_is_warned_not_billed(self):
        self.e.add_reading("RR1001", "2026-07-20", "150", "")
        made = self.e.generate_bills("2026-07")
        self.assertEqual([b.rr for b in made], ["RR1001"])
        self.assertTrue(any("RR2001" in m for _, m in self.e.diagnostics))

    def test_rebilling_month_is_idempotent(self):
        self.e.add_reading("RR1001", "2026-07-20", "150", "")
        self.e.generate_bills("2026-07")
        self.assertEqual(self.e.generate_bills("2026-07"), [])

    def test_reading_chain_uses_previous_closing(self):
        self.e.add_reading("RR1001", "2026-07-20", "150", "")
        self.e.add_reading("RR1001", "2026-08-20", "210", "")
        self.e.generate_bills("2026-07")
        b = self.e.generate_bills("2026-08")[0]
        self.assertEqual((b.opening, b.units), (150, 60))


class TestLateInterest(unittest.TestCase):
    """Pack rule: late payment -> 1% x bill total x ceil(days late/30), placed on the
    first bill dated AFTER the payment date. Bill 2026-07-28, total Rs 1270, due 2026-08-12."""

    def setUp(self):
        self.e = engine_with(("RR1001", "DOMESTIC", "3", "120"))
        self.b1 = bill_one(self.e, "RR1001", "2026-07-28", "250")
        self.assertEqual((self.b1.total, self.b1.due_date), (D("1270"), date(2026, 8, 12)))

    def pay(self, d, amt="1270.00", pid=None):
        self.e.record_payment(pid or f"PAY-{d}", "RR1001", "2026-07", d, amt)

    def more_bills(self, *dates):
        out = []
        for d in dates:
            self.e.add_reading("RR1001", d, "250", "")
        for d in dates:
            out.append(self.e.generate_bills(d[:7])[0])
        return out

    def test_paid_on_due_date_no_interest(self):
        self.pay("2026-08-12")
        self.assertEqual(self.more_bills("2026-08-28")[0].interest, D("0.00"))

    def test_paid_one_day_late_one_percent_on_next_bill(self):
        self.pay("2026-08-13")
        b2 = self.more_bills("2026-08-28")[0]
        self.assertEqual(b2.interest, D("12.70"))
        self.assertEqual(b2.interest_detail, [("PAY-2026-08-13", "2026-07", D("12.70"))])

    def test_exactly_30_days_late_is_one_period(self):
        self.pay("2026-09-11")                                  # 30 days after 08-12
        b2, b3 = self.more_bills("2026-08-28", "2026-09-28")
        self.assertEqual((b2.interest, b3.interest), (D("0.00"), D("12.70")))   # goes on first bill AFTER 09-11

    def test_31_days_late_is_two_periods(self):
        self.pay("2026-09-12")
        b2, b3 = self.more_bills("2026-08-28", "2026-09-28")
        self.assertEqual((b2.interest, b3.interest), (D("0.00"), D("25.40")))

    def test_unpaid_bill_attracts_no_interest(self):
        b2, b3 = self.more_bills("2026-08-28", "2026-09-28")
        self.assertEqual((b2.interest, b3.interest), (D("0.00"), D("0.00")))

    def test_payment_on_next_bill_date_goes_to_following_bill(self):
        self.pay("2026-08-28")                                  # same day as the next bill: not AFTER
        b2, b3 = self.more_bills("2026-08-28", "2026-09-28")
        self.assertEqual((b2.interest, b3.interest), (D("0.00"), D("12.70")))

    def test_interest_charged_once_only(self):
        self.pay("2026-08-13")
        b2, b3 = self.more_bills("2026-08-28", "2026-09-28")
        self.assertEqual((b2.interest, b3.interest), (D("12.70"), D("0.00")))

    def test_interest_is_not_taxed(self):
        self.pay("2026-08-13")
        b2 = self.more_bills("2026-08-28")[0]
        self.assertEqual(b2.tax, D("29.70"))                    # 9% of fixed 330 only
        self.assertEqual(b2.energy + b2.fixed + b2.pf_penalty + b2.tax + b2.interest + b2.rounding, b2.total)

    def test_interest_base_is_bill_total_not_payment_amount(self):
        self.pay("2026-08-13", "1000.00")                       # short payment (WARN) - rule uses the bill total
        self.assertEqual(self.more_bills("2026-08-28")[0].interest, D("12.70"))

    def test_two_late_payments_sum_on_one_bill(self):
        self.pay("2026-08-13")                                  # July bill late
        e = self.e
        e.add_reading("RR1001", "2026-08-28", "250", "")
        b2 = e.generate_bills("2026-08")[0]                     # carries 12.70
        e.record_payment("PAY-X", "RR1001", "2026-08", "2026-09-20", str(b2.total))   # b2 due 09-12 -> 8 days late
        e.add_reading("RR1001", "2026-09-28", "250", "")
        b3 = e.generate_bills("2026-09")[0]
        self.assertEqual(b3.interest, (b2.total * D("0.01")).quantize(D("0.01")))


class TestPaymentValidation(unittest.TestCase):
    def setUp(self):
        self.e = engine_with(("RR1001", "DOMESTIC", "3", "120"))
        self.b = bill_one(self.e, "RR1001", "2026-07-28", "250")

    def err(self, *args):
        with self.assertRaises(ValidationError) as cm:
            self.e.record_payment(*args)
        return cm.exception.code

    def test_overpayment_rejected(self):          self.assertEqual(self.err("P1", "RR1001", "2026-07", "2026-08-01", "1270.01"), "VR-19")
    def test_before_bill_date_rejected(self):     self.assertEqual(self.err("P1", "RR1001", "2026-07", "2026-07-27", "100"), "VR-18")
    def test_unknown_rr(self):                    self.assertEqual(self.err("P1", "RR7777", "2026-07", "2026-08-01", "100"), "VR-13")
    def test_bad_amount(self):                    self.assertEqual(self.err("P1", "RR1001", "2026-07", "2026-08-01", "-5"), "VR-12")

    def test_duplicate_payment_id(self):
        self.e.record_payment("P1", "RR1001", "2026-07", "2026-08-01", "100")
        self.assertEqual(self.err("P1", "RR1001", "2026-07", "2026-08-02", "100"), "VR-17")

    def test_payment_for_future_bill_is_held_then_applied(self):
        self.e.record_payment("P2", "RR1001", "2026-08", "2026-09-01", "50")
        self.assertEqual(len(self.e.pending_payments), 1)
        bill_one(self.e, "RR1001", "2026-08-28", "300")
        self.assertEqual(self.e.pending_payments, [])
        self.assertEqual(self.e.bills[("RR1001", "2026-08")].paid, D("50"))


class TestSummary(unittest.TestCase):
    def test_summary_reconciles_and_splits_by_category(self):
        e = engine_with(("RR1001", "DOMESTIC", "3", "120"), ("RR1002", "DOMESTIC", "2", "0"),
                        ("RR2001", "COMMERCIAL", "5", "1000"))
        e.add_reading("RR1001", "2026-07-28", "250", "")
        e.add_reading("RR1002", "2026-07-28", "0", "")
        e.add_reading("RR2001", "2026-07-25", "1150", "0.85")
        e.generate_bills("2026-07")
        e.record_payment("P1", "RR1001", "2026-07", "2026-08-01", "1270")
        e.record_payment("P2", "RR2001", "2026-07", "2026-08-30", "1000")
        s = e.collection_summary("2026-07")
        self.assertEqual((s["DOMESTIC"]["bills"], s["COMMERCIAL"]["bills"]), (2, 1))
        self.assertEqual(s["DOMESTIC"]["billed"], D("1270") + D("240"))
        self.assertEqual(s["DOMESTIC"]["collected"], D("1270"))
        self.assertEqual(s["COMMERCIAL"]["outstanding"], D("1503"))
        for r in s.values():
            self.assertEqual(r["energy"] + r["fixed"] + r["pf_penalty"] + r["tax"] + r["interest"] + r["rounding"], r["billed"])
        asof = e.collection_summary("2026-07", date(2026, 8, 15))
        self.assertEqual(asof["COMMERCIAL"]["collected"], D("0.00"))


if __name__ == "__main__":
    unittest.main()
