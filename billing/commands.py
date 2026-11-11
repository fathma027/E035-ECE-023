"""Command-file interpreter - grammar fixed by the official pack:

    COMMAND_NAME|arg1|arg2|...      one per line, processed top to bottom,
    lines starting with '#' are comments, blank lines ignored.

  LOAD_CONSUMERS|file      LOAD_READINGS|file      LOAD_PAYMENTS|file
  GENERATE_BILLS|YYYY-MM   (generate + print that month's bills; run months in order)
  COLLECTION_SUMMARY|YYYY-MM   (print the per-category summary)
Extras: REGISTER|rr|category|kw|start     PAYMENT|id|rr|YYYY-MM|date|amount

Files written to the output directory (default ./output):
  bills.csv, collection_summary.csv  - exact evaluation formats (see outputs.py)
Human-readable bills/summary go to `out` (stdout); ERROR/WARN/INFO go to `err`
(stderr). Relative input paths resolve against the command file's folder.
"""
import os
import sys

from . import io_files
from . import validation as v
from .engine import BillingEngine
from .outputs import write_bills_csv, write_summary_csv
from .report import format_bill, format_summary
from .validation import ValidationError


class CommandRunner:
    def __init__(self, engine=None, out=None, err=None, base_dir=".", out_dir="output"):
        self.engine = engine or BillingEngine()
        self.out = out or sys.stdout
        self.err = err or sys.stderr
        self.base_dir = base_dir
        self.out_dir = out_dir
        self._diag_seen = 0
        self.error_count = 0
        self.summaries = {}

    def _path(self, p):
        return p if os.path.isabs(p) else os.path.join(self.base_dir, p)

    def _flush_diag(self):
        for level, msg in self.engine.diagnostics[self._diag_seen:]:
            if level == "ERROR":
                self.error_count += 1
            print(f"{level}: {msg}", file=self.err)
        self._diag_seen = len(self.engine.diagnostics)

    def run_file(self, path):
        self.base_dir = os.path.dirname(os.path.abspath(path))
        with open(path, encoding="utf-8-sig") as f:
            for n, raw in enumerate(f, 1):
                self.run_line(raw, n)
        for p in self.engine.pending_payments:
            self.engine.diag("ERROR", f"payment {p.payment_id}: no bill found for {p.rr} {p.bill_month}")
        self._flush_diag()

    def run_line(self, raw, lineno=0):
        line = raw.strip()
        if not line or line.startswith("#"):
            return
        try:
            parts = [x.strip() for x in line.split("|")]
            self._dispatch(parts[0].upper(), parts[1:])
        except ValidationError as e:
            self.engine.diag("ERROR", f"command line {lineno}: {e}")
        except (OSError, ValueError, IndexError) as e:
            self.engine.diag("ERROR", f"command line {lineno}: cannot execute '{line}': {e}")
        self._flush_diag()

    def _need(self, cmd, a, n):
        if len(a) < n:
            raise ValidationError("CMD-02", f"{cmd} needs {n} argument(s), got {len(a)}")

    def _dispatch(self, cmd, a):
        e = self.engine
        if cmd == "LOAD_CONSUMERS":
            self._need(cmd, a, 1)
            ok, bad = io_files.load_consumers(e, self._path(a[0]))
            e.diag("INFO", f"LOAD_CONSUMERS: {ok} registered, {bad} rejected")
        elif cmd == "LOAD_READINGS":
            self._need(cmd, a, 1)
            ok, bad = io_files.load_readings(e, self._path(a[0]))
            e.diag("INFO", f"LOAD_READINGS: {ok} accepted, {bad} rejected")
        elif cmd == "LOAD_PAYMENTS":
            self._need(cmd, a, 1)
            ok, bad = io_files.load_payments(e, self._path(a[0]))
            e.apply_pending_payments()
            e.diag("INFO", f"LOAD_PAYMENTS: {ok} accepted, {bad} rejected")
        elif cmd == "REGISTER":
            self._need(cmd, a, 4)
            e.register_consumer(*a[:4])
        elif cmd == "PAYMENT":
            self._need(cmd, a, 5)
            e.record_payment("" if a[0] in ("", "-") else a[0], *a[1:5])
        elif cmd == "GENERATE_BILLS":
            self._need(cmd, a, 1)
            month = v.parse_month(a[0])
            bills = e.generate_bills(month)
            for b in bills:
                print(format_bill(b), file=self.out)
                print(file=self.out)
            e.diag("INFO", f"GENERATE_BILLS {month}: {len(bills)} bill(s) generated")
            write_bills_csv(os.path.join(self.out_dir, "bills.csv"), e.bills.values())
        elif cmd == "COLLECTION_SUMMARY":
            self._need(cmd, a, 1)
            month = v.parse_month(a[0])
            asof = v.parse_date(a[1], "as-of date", "VR-10") if len(a) > 1 else None
            rows = e.collection_summary(month, asof)
            self.summaries[month] = rows
            print(format_summary(month, rows, asof), file=self.out)
            print(file=self.out)
            write_summary_csv(os.path.join(self.out_dir, "collection_summary.csv"), self.summaries)
        else:
            raise ValidationError("CMD-01", f"unknown command '{cmd}'")
