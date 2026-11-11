"""CSV loaders. A bad row never aborts a load: it is reported (with its line
number) and skipped, and the good rows are still processed."""
import csv
from typing import Callable, Dict, List

from .validation import ValidationError


def _rows(path: str, required: List[str]):
    f = open(path, newline="", encoding="utf-8-sig")
    reader = csv.DictReader(f)
    reader.fieldnames = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in required if c not in reader.fieldnames]
    if missing:
        f.close()
        raise ValidationError("VR-20", f"{path}: missing column(s) {', '.join(missing)}")
    return f, reader


def _load(engine, path, required, handler: Callable[[Dict[str, str]], None], label):
    ok = bad = 0
    f, reader = _rows(path, required)
    with f:
        for row in reader:
            if not any((v or "").strip() for v in row.values()):
                continue
            try:
                handler({k: (v or "") for k, v in row.items() if k})
                ok += 1
            except ValidationError as e:
                bad += 1
                engine.diag("ERROR", f"{label} line {reader.line_num}: {e}")
    return ok, bad


def load_consumers(engine, path):
    return _load(engine, path, ["rr_number", "category", "sanctioned_load_kw", "meter_start_reading"],
                 lambda r: engine.register_consumer(r["rr_number"], r["category"],
                                                    r["sanctioned_load_kw"], r["meter_start_reading"]),
                 "consumers")


def load_readings(engine, path):
    return _load(engine, path, ["rr_number", "reading_date", "closing_reading", "avg_pf"],
                 lambda r: engine.add_reading(r["rr_number"], r["reading_date"],
                                              r["closing_reading"], r["avg_pf"]),
                 "readings")


def load_payments(engine, path):
    return _load(engine, path, ["rr_number", "bill_month", "payment_date", "amount_rs"],
                 lambda r: engine.record_payment(r.get("payment_id", ""), r["rr_number"],
                                                 r["bill_month"], r["payment_date"], r["amount_rs"]),
                 "payments")
