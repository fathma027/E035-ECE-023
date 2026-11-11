"""Deterministic text rendering of bills and the collection summary."""
from .config import CATEGORIES
from .money import fmt

W = 64
RULE = "=" * W
THIN = "-" * W


def _row(label: str, amount: str) -> str:
    return f"{label:<{W - 14}}{amount:>14}"


def format_bill(b) -> str:
    out = [RULE, f"{'ELECTRICITY BILL - ' + b.month:^{W}}", RULE,
           f"Bill No         : {b.bill_id}",
           f"RR No           : {b.rr:<20}Category : {b.category}",
           f"Sanctioned load : {fmt(b.load_kw)} kW",
           f"Bill date       : {b.bill_date}   Due date : {b.due_date}",
           f"Meter reading   : opening {b.opening:05d}  closing {b.closing:05d}  units {b.units}"]
    if b.rollover:
        out.append("                  (meter rollover applied: 99999 -> 00000)")
    if b.pf is not None:
        out.append(f"Average PF      : {b.pf}")
    out.append(THIN)
    for s in b.slabs:
        out.append(_row(f"  Units {s.from_unit:>5} - {s.to_unit:<5} {s.units:>5} x Rs {s.rate}", fmt(s.amount)))
    out.append(_row("Energy charge", fmt(b.energy)))
    out.append(_row(f"Fixed charge ({fmt(b.load_kw)} kW x Rs {int(b.fixed / b.load_kw)})", fmt(b.fixed)))
    if b.category == "COMMERCIAL":
        out.append(_row(f"PF penalty ({int(b.pf_pct * 100)}% of energy)", fmt(b.pf_penalty)))
    else:
        out.append(_row("PF penalty (not applicable)", fmt(b.pf_penalty)))
    out.append(_row("Electricity tax (9%)", fmt(b.tax)))
    out.append(_row("Late payment interest", fmt(b.interest)))
    for pid, m, amt in b.interest_detail:
        out.append(_row(f"  late payment {pid} (bill {m})", fmt(amt)))
    out.append(_row("Rounding adjustment", fmt(b.rounding)))
    out.append(THIN)
    out.append(_row("TOTAL PAYABLE (Rs)", fmt(b.total)))
    out.append(RULE)
    return "\n".join(out)


def format_summary(month: str, rows: dict, asof=None) -> str:
    cols = [("bills", "Bills", 6), ("units", "Units", 9), ("energy", "Energy", 12),
            ("fixed", "Fixed", 12), ("pf_penalty", "PF pen.", 10), ("tax", "Tax", 11),
            ("interest", "Interest", 10), ("late_payments", "Late", 5), ("rounding", "Round", 8), ("billed", "Billed", 13),
            ("collected", "Collected", 13), ("outstanding", "Outstanding", 13)]
    width = 12 + sum(w + 1 for _, _, w in cols)
    title = f"MONTHLY COLLECTION SUMMARY - {month}" + (f" (payments up to {asof})" if asof else "")
    lines = ["=" * width, title, "=" * width,
             f"{'Category':<12}" + "".join(f" {h:>{w}}" for _, h, w in cols), "-" * width]
    total = {k: 0 for k, _, _ in cols}
    for cat in CATEGORIES:
        r = rows[cat]
        for k, _, _ in cols:
            total[k] += r[k]
        lines.append(f"{cat:<12}" + "".join(f" {_cell(k, r[k]):>{w}}" for k, _, w in cols))
    lines.append("-" * width)
    lines.append(f"{'TOTAL':<12}" + "".join(f" {_cell(k, total[k]):>{w}}" for k, _, w in cols))
    eff = (total["collected"] / total["billed"] * 100) if total["billed"] else 0
    lines += ["=" * width, f"Collection efficiency: {eff:.2f}%"]
    return "\n".join(lines)


def _cell(key, value):
    return str(value) if key in ("bills", "units", "late_payments") else fmt(value)
