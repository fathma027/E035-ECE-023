"""Unit tests for BR-01 .. BR-06 and BR-08 (pure tariff functions)."""
import unittest
from decimal import Decimal as D

from billing.tariff import (electricity_tax, energy_charge, fixed_charge,
                            pf_penalty, units_consumed)
from billing.money import q2, round_rupee


class TestDomesticSlabs(unittest.TestCase):          # BR-01
    def energy(self, u):
        return energy_charge("DOMESTIC", u)[0]

    def test_zero(self):            self.assertEqual(self.energy(0), D("0.00"))
    def test_one_unit(self):        self.assertEqual(self.energy(1), D("4.75"))
    def test_exactly_50(self):      self.assertEqual(self.energy(50), D("237.50"))
    def test_51(self):              self.assertEqual(self.energy(51), D("244.50"))
    def test_exactly_100(self):     self.assertEqual(self.energy(100), D("587.50"))
    def test_101(self):             self.assertEqual(self.energy(101), D("595.75"))
    def test_exactly_200(self):     self.assertEqual(self.energy(200), D("1412.50"))
    def test_201(self):             self.assertEqual(self.energy(201), D("1422.00"))
    def test_300(self):             self.assertEqual(self.energy(300), D("2362.50"))

    def test_130_is_telescopic_not_flat(self):
        total, lines = energy_charge("DOMESTIC", 130)
        self.assertEqual(total, D("835.00"))
        self.assertEqual([(s.from_unit, s.to_unit, s.units) for s in lines],
                         [(1, 50, 50), (51, 100, 50), (101, 130, 30)])
        self.assertNotEqual(total, q2(130 * D("8.25")))        # flat would be 1072.50

    def test_slab_lines_sum_to_total(self):
        for u in range(0, 400):
            total, lines = energy_charge("DOMESTIC", u)
            self.assertEqual(sum(s.units for s in lines), u)
            self.assertEqual(sum((s.amount for s in lines), D("0")), total)


class TestCommercialSlabs(unittest.TestCase):        # BR-02
    def energy(self, u):
        return energy_charge("COMMERCIAL", u)[0]

    def test_zero(self):            self.assertEqual(self.energy(0), D("0.00"))
    def test_exactly_100(self):     self.assertEqual(self.energy(100), D("900.00"))
    def test_101(self):             self.assertEqual(self.energy(101), D("910.50"))
    def test_150(self):             self.assertEqual(self.energy(150), D("1425.00"))
    def test_400(self):             self.assertEqual(self.energy(400), D("4050.00"))


class TestFixedCharge(unittest.TestCase):            # BR-03
    def test_domestic(self):        self.assertEqual(fixed_charge("DOMESTIC", D("3.00")), D("330.00"))
    def test_commercial(self):      self.assertEqual(fixed_charge("COMMERCIAL", D("5.00")), D("800.00"))
    def test_fractional_kw(self):   self.assertEqual(fixed_charge("DOMESTIC", D("1.25")), D("137.50"))
    def test_commercial_half_kw(self): self.assertEqual(fixed_charge("COMMERCIAL", D("2.50")), D("400.00"))


class TestPFPenalty(unittest.TestCase):              # BR-04
    E = D("1425.00")

    def pen(self, pf, cat="COMMERCIAL"):
        return pf_penalty(cat, self.E, D(pf))

    def test_exactly_090_no_penalty(self):   self.assertEqual(self.pen("0.90"), (D("0.00"), D("0")))
    def test_above_090_no_penalty(self):     self.assertEqual(self.pen("0.97")[0], D("0.00"))
    def test_089_is_one_percent(self):       self.assertEqual(self.pen("0.89")[0], D("14.25"))
    def test_085_is_five_percent(self):      self.assertEqual(self.pen("0.85")[0], D("71.25"))
    def test_076_is_14_percent(self):        self.assertEqual(self.pen("0.76")[0], D("199.50"))
    def test_075_hits_cap_exactly(self):      self.assertEqual(self.pen("0.75")[0], D("213.75"))
    def test_070_cap_applies(self):
        amt, pct = self.pen("0.70")
        self.assertEqual(pct, D("0.15"))                    # 20 steps -> 20% -> capped to 15%
        self.assertEqual(amt, D("213.75"))
    def test_partial_step_not_counted(self): self.assertEqual(self.pen("0.895")[0], D("0.00"))
    def test_domestic_never_penalised(self): self.assertEqual(self.pen("0.50", "DOMESTIC")[0], D("0.00"))
    def test_zero_energy_zero_penalty(self):
        self.assertEqual(pf_penalty("COMMERCIAL", D("0.00"), D("0.70"))[0], D("0.00"))


class TestTax(unittest.TestCase):                    # BR-05
    def test_tax_base_includes_penalty(self):
        # (1425.00 + 800.00 + 71.25) * 9% = 206.6625 -> 206.66
        self.assertEqual(electricity_tax(D("1425.00"), D("800.00"), D("71.25")), D("206.66"))
    def test_zero_consumption_still_taxed(self):
        self.assertEqual(electricity_tax(D("0.00"), D("220.00"), D("0.00")), D("19.80"))
    def test_half_up(self):
        self.assertEqual(electricity_tax(D("0.00"), D("0.50"), D("0.00")), D("0.05"))  # 0.045 -> 0.05


class TestRollover(unittest.TestCase):               # BR-06
    def test_normal(self):           self.assertEqual(units_consumed(120, 250), (130, False))
    def test_equal_is_zero(self):    self.assertEqual(units_consumed(500, 500), (0, False))
    def test_brief_case(self):       self.assertEqual(units_consumed(99980, 12), (32, True))
    def test_wrap_to_zero(self):     self.assertEqual(units_consumed(99999, 0), (1, True))
    def test_max_to_max(self):       self.assertEqual(units_consumed(99999, 99999), (0, False))
    def test_open_zero(self):        self.assertEqual(units_consumed(0, 99999), (99999, False))
    def test_big_wrap(self):         self.assertEqual(units_consumed(99820, 50), (230, True))


class TestRounding(unittest.TestCase):               # BR-08
    def test_half_up_2dp(self):
        self.assertEqual(q2(D("2.005")), D("2.01"))
        self.assertEqual(q2(D("2.004")), D("2.00"))
    def test_rupee_half_up(self):
        self.assertEqual(round_rupee(D("100.50")), D("101"))
        self.assertEqual(round_rupee(D("100.49")), D("100"))


if __name__ == "__main__":
    unittest.main()
