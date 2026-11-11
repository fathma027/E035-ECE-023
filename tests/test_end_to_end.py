"""End-to-end tests on the OFFICIAL 10 SECONDS sample pack (data/): every planted
scenario from the pack README, an independent oracle, reconciliation invariants,
golden CSV snapshots, determinism and robustness against bad input."""
import csv
import io
import os
import tempfile
import unittest
from decimal import Decimal as D, ROUND_HALF_UP

from billing.commands import CommandRunner
from billing.outputs import BILL_COLS, SUMMARY_COLS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, "data", "commands.txt")


def run_commands(path, out_dir):
    out, err = io.StringIO(), io.StringIO()
    runner = CommandRunner(out=out, err=err, out_dir=out_dir)
    runner.run_file(path)
    return runner, out.getvalue(), err.getvalue()


def q(x):
    return D(x).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def oracle(category, load, opening, closing, pf):
    """Independent closed-form formulation used only to cross-check the engine."""
    units = closing - opening if closing >= opening else 99999 - opening + closing + 1
    u = D(units)
    if category == "DOMESTIC":
        e = (D("4.75") * min(u, 50) + D("7.00") * max(D(0), min(u, 100) - 50)
             + D("8.25") * max(D(0), min(u, 200) - 100) + D("9.50") * max(D(0), u - 200))
        fixed = D(load) * 110
    else:
        e = D("9.00") * min(u, 100) + D("10.50") * max(D(0), u - 100)
        fixed = D(load) * 160
    e, fixed = q(e), q(fixed)
    pen = D("0.00")
    if category == "COMMERCIAL" and pf < D("0.90"):
        pen = q(e * D(min(int((D("0.90") - pf) * 100), 15)) / 100)
    return e, fixed, pen, q((e + fixed + pen) * D("0.09")), units


class PackCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.runner, cls.out, cls.err = run_commands(PACK, cls.tmp.name)
        cls.eng = cls.runner.engine
        cls.bills = cls.eng.bills

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def bill(self, rr, month):
        return self.bills[(rr, month)]


class TestPackGeneral(PackCase):
    def test_clean_run(self):
        self.assertEqual(self.runner.error_count, 0, self.err)
        self.assertNotIn("WARN", self.err)             # every payment equals its bill total

    def test_counts(self):
        cats = [c.category for c in self.eng.consumers.values()]
        self.assertEqual((len(cats), cats.count("DOMESTIC"), cats.count("COMMERCIAL")), (40, 28, 12))
        self.assertEqual(len(self.bills), 120)

    def test_matches_independent_oracle(self):
        last = {rr: c.start_reading for rr, c in self.eng.consumers.items()}
        for (rr, month), b in sorted(self.bills.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            c = self.eng.consumers[rr]
            e, f, p, t, units = oracle(c.category, c.load_kw, last[rr], b.closing, b.pf)
            self.assertEqual((b.energy, b.fixed, b.pf_penalty, b.tax, b.units), (e, f, p, t, units), b.bill_id)
            last[rr] = b.closing

    def test_every_bill_reconciles(self):
        for b in self.bills.values():
            self.assertEqual(b.energy + b.fixed + b.pf_penalty + b.tax + b.interest + b.rounding, b.total, b.bill_id)
            self.assertEqual(b.total, b.total.to_integral_value())
            self.assertLessEqual(abs(b.rounding), D("0.50"))

    def test_every_pack_payment_equals_engine_total(self):
        """Independent evidence: the pack's payment amounts were produced from the
        official totals, so equality on all 108 means our totals (incl. interest) agree."""
        n = 0
        for b in self.bills.values():
            for p in b.payments:
                self.assertEqual(p.amount, b.total, p.payment_id)
                n += 1
        self.assertEqual(n, 108)


class TestPlantedScenarios(PackCase):
    # --- slab boundaries -------------------------------------------------
    def test_exactly_50_units(self):
        b = self.bill("RR-BT-62186", "2026-08")
        self.assertEqual((b.opening, b.closing, b.units, b.energy), (58444, 58494, 50, D("237.50")))

    def test_exactly_100_units(self):
        b = self.bill("RR-BK-83373", "2026-09")
        self.assertEqual((b.units, b.energy), (100, D("587.50")))

    def test_exactly_200_units(self):
        b = self.bill("RR-JN-10028", "2026-10")
        self.assertEqual((b.opening, b.closing, b.units, b.energy), (55310, 55510, 200, D("1412.50")))

    def test_201_units_one_unit_at_950(self):
        b = self.bill("RR-JP-10672", "2026-09")
        self.assertEqual((b.units, b.energy), (201, D("1412.50") + D("9.50")))

    # --- PF --------------------------------------------------------------
    def test_pf_exactly_090_no_penalty(self):
        b = self.bill("RR-BK-21066", "2026-10")
        self.assertEqual((b.units, b.pf, b.pf_penalty), (1060, D("0.90"), D("0.00")))

    def test_pf_070_cap_15_percent(self):
        b = self.bill("RR-JP-78161", "2026-08")
        self.assertEqual((b.units, b.energy, b.pf_pct, b.pf_penalty), (1060, D("10980.00"), D("0.15"), D("1647.00")))

    def test_pf_089_one_percent(self):
        b = self.bill("RR-BG-50108", "2026-08")
        self.assertEqual((b.units, b.energy, b.pf_pct, b.pf_penalty), (432, D("4386.00"), D("0.01"), D("43.86")))

    # --- rollover ---------------------------------------------------------
    def test_rollover_99980_to_00012(self):
        b = self.bill("RR-BT-62684", "2026-09")
        self.assertEqual((b.opening, b.closing, b.units, b.rollover), (99980, 12, 32, True))

    def test_second_rollover(self):
        b = self.bill("RR-BK-69000", "2026-10")
        self.assertEqual((b.opening, b.closing, b.units, b.rollover), (99731, 285, 554, True))
        self.assertEqual(sum(1 for x in self.bills.values() if x.rollover), 2)

    # --- zero consumption --------------------------------------------------
    def test_zero_consumption_months(self):
        keys = [("RR-BK-70433", "2026-08"), ("RR-BG-75333", "2026-08"), ("RR-JN-75217", "2026-09"), ("RR-JN-75217", "2026-10")]
        for k in keys:
            b = self.bills[k]
            self.assertEqual((b.units, b.energy, b.pf_penalty), (0, D("0.00"), D("0.00")), k)
            self.assertGreater(b.fixed, 0)
            self.assertEqual(b.tax, q(b.fixed * D("0.09")), k)                 # tax on fixed charge alone
        self.assertEqual(sum(1 for x in self.bills.values() if x.units == 0), 4)

    def test_zero_consumption_commercial_pf_zero_accepted(self):
        zero_pf = [b for b in self.bills.values() if b.category == "COMMERCIAL" and b.pf == D("0.00")]
        self.assertTrue(zero_pf)
        self.assertTrue(all(b.pf_penalty == D("0.00") and b.units == 0 for b in zero_pf))

    # --- due date boundary and late payments ------------------------------------
    def test_pay_0035_on_due_date_no_interest(self):
        b = self.bill("RR-BT-99048", "2026-08")
        self.assertEqual((str(b.bill_date), str(b.due_date)), ("2026-08-04", "2026-08-19"))
        self.assertEqual([p.pay_date.isoformat() for p in b.payments], ["2026-08-19"])
        self.assertEqual(self.bill("RR-BT-99048", "2026-09").interest, D("0.00"))

    def interest_of(self, rr, month, pid):
        return {p: a for p, _, a in self.bill(rr, month).interest_detail}.get(pid)

    def test_pay_0036_one_day_late_one_percent_on_next_bill(self):
        aug = self.bill("RR-JN-24514", "2026-08")
        self.assertEqual(str(aug.due_date), "2026-08-21")
        self.assertEqual(self.interest_of("RR-JN-24514", "2026-09", "PAY-0036"), q(aug.total * D("0.01")))

    def test_pay_0037_12_days_late(self):
        aug = self.bill("RR-BT-61171", "2026-08")
        self.assertEqual(self.interest_of("RR-BT-61171", "2026-09", "PAY-0037"), q(aug.total * D("0.01")))

    def test_pay_0070_exactly_30_days_one_period(self):
        aug = self.bill("RR-BK-51504", "2026-08")          # paid 09-17, after the 09-03 bill -> lands on October
        self.assertEqual(str(aug.due_date), "2026-08-18")
        self.assertEqual(self.interest_of("RR-BK-51504", "2026-10", "PAY-0070"), q(aug.total * D("0.01")))

    def test_pay_0078_31_days_two_periods(self):
        aug = self.bill("RR-BG-72393", "2026-08")          # paid 09-21, after the 09-04 bill -> lands on October
        self.assertEqual(str(aug.due_date), "2026-08-21")
        self.assertEqual(self.interest_of("RR-BG-72393", "2026-10", "PAY-0078"), q(aug.total * D("0.02")))

    def test_pay_0080_44_days_two_periods_lands_on_october_bill(self):
        aug = self.bill("RR-JN-61032", "2026-08")
        self.assertEqual(self.interest_of("RR-JN-61032", "2026-10", "PAY-0080"), q(aug.total * D("0.02")))
        self.assertEqual(self.bill("RR-JN-61032", "2026-09").interest, D("0.00"))

    def test_pay_0079_lands_on_october_bill(self):
        sep = self.bill("RR-BT-77012", "2026-09")
        self.assertEqual(self.interest_of("RR-BT-77012", "2026-10", "PAY-0079"), q(sep.total * D("0.01")))

    def test_exactly_six_late_payments_and_no_stray_interest(self):
        late = [(b.bill_id, p.payment_id) for b in self.bills.values() for p in b.payments if p.pay_date > b.due_date]
        self.assertEqual(len(late), 6)
        charged = sum(len(b.interest_detail) for b in self.bills.values())
        self.assertEqual(charged, 6)

    # --- rounding, fractional load, unpaid -----------------------------------
    def test_rounding_exactly_50_paise_half_up(self):
        b = self.bill("RR-JP-94514", "2026-09")
        self.assertEqual(b.rounding, D("0.50"))

    def test_fractional_load(self):
        for c in self.eng.consumers.values():
            if c.load_kw == D("2.5") and c.category == "DOMESTIC":
                self.assertEqual(self.bill(c.rr, "2026-08").fixed, D("275.00"))
                break
        else:
            self.fail("no 2.5 kW domestic consumer in pack")

    def test_unpaid_october_bills_outstanding_without_interest(self):
        unpaid = [b for (rr, m), b in self.bills.items() if m == "2026-10" and not b.payments]
        self.assertTrue(unpaid)
        s = self.eng.collection_summary("2026-10")
        self.assertEqual(sum(r["outstanding"] for r in s.values()), sum(b.total for b in unpaid))


class TestPackOutputFiles(PackCase):
    def rows(self, name):
        with open(os.path.join(self.tmp.name, name), newline="") as f:
            return list(csv.reader(f))

    def test_bills_csv_format(self):
        rows = self.rows("bills.csv")
        self.assertEqual(rows[0], BILL_COLS)
        self.assertEqual(len(rows), 121)
        self.assertEqual([(r[3], r[1]) for r in rows[1:]], sorted((r[3], r[1]) for r in rows[1:]))   # month, then rr
        r = next(x for x in rows if x[1] == "RR-BT-62684" and x[3] == "2026-09")
        self.assertEqual((r[0], r[6], r[7], r[8]), ("BL-202609-RR-BT-62684", "99980", "00012", "32"))
        for x in rows[1:]:
            self.assertRegex(x[15], r"^\d+\.00$")        # total: whole rupee, 2 dp text

    def test_summary_csv_format(self):
        rows = self.rows("collection_summary.csv")
        self.assertEqual(rows[0], SUMMARY_COLS)
        self.assertEqual([(r[0], r[1]) for r in rows[1:]],
                         [(m, c) for m in ("2026-08", "2026-09", "2026-10") for c in ("DOMESTIC", "COMMERCIAL")])
        self.assertEqual(sum(int(r[7]) for r in rows[1:]), 6)           # six late payments

    def test_summary_equals_sum_of_bills(self):
        for r in self.rows("collection_summary.csv")[1:]:
            mine = [b for (rr, m), b in self.bills.items() if m == r[0] and b.category == r[1]]
            self.assertEqual(int(r[2]), len(mine))
            self.assertEqual(D(r[4]), sum(b.total for b in mine))
            self.assertEqual(D(r[5]) + D(r[6]), D(r[4]))
            self.assertEqual(D(r[8]), sum(b.interest for b in mine))

    def test_golden_snapshots(self):
        for name in ("bills.csv", "collection_summary.csv"):
            with open(os.path.join(ROOT, "expected", name), encoding="utf-8") as f:
                with open(os.path.join(self.tmp.name, name), encoding="utf-8") as g:
                    self.assertEqual(g.read(), f.read(), name)

    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            _, out2, _ = run_commands(PACK, d)
            self.assertEqual(out2, self.out)


class TestStandaloneEngine(PackCase):
    """standalone/billing_engine.py is an independently written single-file engine;
    byte-identical output from both implementations is strong evidence of correctness."""

    def test_outputs_identical_to_package(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("standalone_engine", os.path.join(ROOT, "standalone", "billing_engine.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        data = os.path.join(ROOT, "data")
        with tempfile.TemporaryDirectory() as d:
            eng, months = mod.run_commands(os.path.join(data, "commands.txt"), data)
            eng.write_bills_csv(os.path.join(d, "bills.csv"))
            eng.write_summary_csv(os.path.join(d, "collection_summary.csv"), months)
            for name in ("bills.csv", "collection_summary.csv"):
                with open(os.path.join(d, name)) as a, open(os.path.join(self.tmp.name, name)) as b:
                    self.assertEqual(a.read(), b.read(), name)


class TestRobustness(unittest.TestCase):
    def write(self, folder, name, text):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
            f.write(text)

    def test_bad_rows_are_reported_and_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, "c.csv", "rr_number,consumer_name,category,sanctioned_load_kw,meter_start_reading\n"
                                   "RR-AA-00001,A,DOMESTIC,3.0,00120\nRR-AA-00002,B,INDUSTRIAL,3.0,0\nRR-AA-00003,C,DOMESTIC,-2,0\n"
                                   "RR-AA-00001,D,DOMESTIC,1.0,0\nRR-CC-00001,E,COMMERCIAL,5.0,100\n")
            self.write(d, "r.csv", "rr_number,reading_date,closing_reading,avg_pf\n"
                                   "RR-AA-00001,2026-07-28,00250,NONE\nRR-CC-00001,2026-07-28,00300,NONE\nRR-ZZ-99999,2026-07-28,5,NONE\n"
                                   "RR-CC-00001,2026-07-28,00300,0.85\n")
            self.write(d, "cmd.txt", "LOAD_CONSUMERS|c.csv\nLOAD_READINGS|r.csv\nBOGUS|1\nGENERATE_BILLS|2026-07\n")
            runner, out, err = run_commands(os.path.join(d, "cmd.txt"), os.path.join(d, "o"))
            self.assertEqual((len(runner.engine.consumers), len(runner.engine.bills)), (2, 2))
            for code in ("VR-02", "VR-03", "VR-06", "VR-08", "VR-13", "CMD-01"):
                self.assertIn(code, err)
            self.assertIn("RR-AA-00001-2026-07", out)
            self.assertTrue(os.path.exists(os.path.join(d, "o", "bills.csv")))

    def test_missing_columns_missing_file_and_comments(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, "c.csv", "rr,cat\nX,Y\n")
            self.write(d, "cmd.txt", "# comment\n\nLOAD_CONSUMERS|c.csv\nLOAD_CONSUMERS|nope.csv\nGENERATE_BILLS\n")
            _, _, err = run_commands(os.path.join(d, "cmd.txt"), os.path.join(d, "o"))
            self.assertIn("VR-20", err)
            self.assertIn("nope.csv", err)
            self.assertIn("CMD-02", err)

    def test_unmatched_payment_reported_at_end(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, "cmd.txt", "REGISTER|RR-AA-00001|DOMESTIC|3.0|0\nPAYMENT|PAY-1|RR-AA-00001|2026-07|2026-08-01|100\n")
            _, _, err = run_commands(os.path.join(d, "cmd.txt"), os.path.join(d, "o"))
            self.assertIn("no bill found", err)


if __name__ == "__main__":
    unittest.main()
