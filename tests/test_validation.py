"""Tests for field validation (VR-xx)."""
import unittest
from decimal import Decimal as D

from billing import validation as v
from billing.validation import ValidationError


def code(fn, *a):
    try:
        fn(*a)
    except ValidationError as e:
        return e.code
    return None


class TestValidation(unittest.TestCase):
    def test_rr(self):
        self.assertEqual(v.parse_rr(" rr1001 "), "RR1001")
        self.assertEqual(v.parse_rr("RR-BG-50108"), "RR-BG-50108")
        self.assertEqual(code(v.parse_rr, ""), "VR-01")
        self.assertEqual(code(v.parse_rr, "R R"), "VR-01")
        self.assertEqual(code(v.parse_rr, "AB"), "VR-01")
        self.assertEqual(code(v.parse_rr, "-RR-BG"), "VR-01")

    def test_category(self):
        self.assertEqual(v.parse_category("domestic"), "DOMESTIC")
        self.assertEqual(code(v.parse_category, "INDUSTRIAL"), "VR-02")

    def test_load(self):
        self.assertEqual(v.parse_load("2.5"), D("2.5"))
        for bad in ("0", "-1", "abc", "", "1.234", "NaN", "Infinity"):
            self.assertEqual(code(v.parse_load, bad), "VR-03", bad)

    def test_meter(self):
        self.assertEqual(v.parse_meter("00012", "x", "VR-07"), 12)
        self.assertEqual(v.parse_meter("99999", "x", "VR-07"), 99999)
        for bad in ("100000", "-5", "12.5", "", "abc"):
            self.assertEqual(code(v.parse_meter, bad, "x", "VR-07"), "VR-07", bad)

    def test_date(self):
        self.assertEqual(str(v.parse_date("2026-02-28", "d", "VR-05")), "2026-02-28")
        self.assertEqual(code(v.parse_date, "2026-02-30", "d", "VR-05"), "VR-05")
        self.assertEqual(code(v.parse_date, "28/02/2026", "d", "VR-05"), "VR-05")

    def test_pf(self):
        self.assertEqual(v.parse_pf("0.9", "COMMERCIAL"), D("0.9"))
        self.assertEqual(v.parse_pf("1", "COMMERCIAL"), D("1"))
        self.assertEqual(v.parse_pf("0.00", "COMMERCIAL"), D("0.00"))     # legal: zero-consumption commercial month
        self.assertIsNone(v.parse_pf("NONE", "DOMESTIC"))
        self.assertIsNone(v.parse_pf("", "DOMESTIC"))
        self.assertIsNone(v.parse_pf("0.5", "DOMESTIC"))
        self.assertEqual(code(v.parse_pf, "", "COMMERCIAL"), "VR-08")
        self.assertEqual(code(v.parse_pf, "NONE", "COMMERCIAL"), "VR-08")
        for bad in ("1.01", "-0.5", "abc"):
            self.assertEqual(code(v.parse_pf, bad, "COMMERCIAL"), "VR-09", bad)

    def test_month_and_amount(self):
        self.assertEqual(v.parse_month("2026-07"), "2026-07")
        self.assertEqual(code(v.parse_month, "2026-13"), "VR-11")
        self.assertEqual(v.parse_amount("100.50"), D("100.50"))
        for bad in ("0", "-1", "1.005", "x"):
            self.assertEqual(code(v.parse_amount, bad), "VR-12", bad)


if __name__ == "__main__":
    unittest.main()
