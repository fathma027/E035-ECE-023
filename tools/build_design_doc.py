#!/usr/bin/env python3
"""Build docs/design_document.pdf (needs reportlab: pip install reportlab).
Worked examples are computed by the engine at build time, so the document can
never drift from the code."""
import os
import sys
from decimal import Decimal as D

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle, Preformatted)

from billing.engine import BillingEngine
from billing.money import fmt
from billing.report import format_bill
from billing.tariff import energy_charge

# ----------------------------------------------------------------- styles
ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, leading=10.5)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8, leading=10)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=15, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#12355b"))
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#1f5a99"))
MONO = ParagraphStyle("mono", fontName="Courier", fontSize=7.6, leading=9.2)
TITLE = ParagraphStyle("title", parent=BODY, fontName="Helvetica-Bold", fontSize=22, leading=27, alignment=TA_CENTER, textColor=colors.HexColor("#12355b"))
SUB = ParagraphStyle("sub", parent=BODY, fontSize=11.5, leading=16, alignment=TA_CENTER)
HEAD_BG = colors.HexColor("#1f5a99")


def P(t, s=BODY): return Paragraph(t, s)


def table(rows, widths, header=True, font=CELL):
    data = []
    for i, r in enumerate(rows):
        data.append([Paragraph(str(c), CELLB if (header and i == 0) else font) for c in r])
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9aa7b5")),
          ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
          ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if header:
        st.append(("BACKGROUND", (0, 0), (-1, 0), HEAD_BG))
        st += [("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f2f6fa")) for i in range(2, len(rows), 2)]
    t.setStyle(TableStyle(st))
    return t


def arch_diagram():
    d = Drawing(170 * mm, 262)

    def box(x, y, w, h, text, fill):
        d.add(Rect(x, y, w, h, fillColor=fill, strokeColor=colors.HexColor("#12355b"), rx=3, ry=3))
        for i, line in enumerate(text.split("\n")):
            d.add(String(x + w / 2, y + h - 11 - i * 9.5, line, textAnchor="middle",
                         fontName="Helvetica-Bold" if i == 0 else "Helvetica", fontSize=7.5 if i else 8.5))

    def arrow(x1, y1, x2, y2):
        d.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor("#12355b")))
        d.add(Line(x2, y2, x2 - 3, y2 + 4 if y2 > y1 else y2 - 4, strokeColor=colors.HexColor("#12355b")))
        d.add(Line(x2, y2, x2 + 3, y2 + 4 if y2 > y1 else y2 - 4, strokeColor=colors.HexColor("#12355b")))

    blue, green, amber = colors.HexColor("#dbe9f7"), colors.HexColor("#dff0d8"), colors.HexColor("#fcf0cf")
    box(10, 214, 470, 38, "Command file  (commands.txt, pipe-separated)\nLOAD_CONSUMERS / LOAD_READINGS / LOAD_PAYMENTS / GENERATE_BILLS / COLLECTION_SUMMARY", amber)
    box(10, 150, 470, 40, "commands.py + io_files.py + outputs.py\nparse, dispatch, per-row error isolation; writes bills.csv, collection_summary.csv", blue)
    box(10, 80, 225, 46, "engine.py  (BillingEngine)\nconsumers, readings, bills, payments,\nbilling pipeline, collection summary", green)
    box(255, 80, 225, 46, "validation.py\nVR-01 .. VR-20 field rules\nValidationError(code, message)", blue)
    box(10, 8, 150, 46, "tariff.py  (pure functions)\nBR-01..06, BR-08:\nslabs, fixed, PF, tax, rollover", green)
    box(170, 8, 150, 46, "interest.py\nBR-07: due date, overdue\nperiods, incremental interest", green)
    box(330, 8, 150, 46, "config.py / money.py\nall rates in ONE place;\nDecimal + ROUND_HALF_UP", amber)
    arrow(245, 214, 245, 190); arrow(245, 150, 125, 126); arrow(245, 150, 365, 126)
    arrow(80, 80, 80, 54); arrow(245, 80, 245, 54); arrow(400, 80, 400, 54)
    return d


# ----------------------------------------------------------------- worked examples (computed live)
def build_examples():
    e = BillingEngine()
    for c in [("RR1001", "DOMESTIC", "3", "120"), ("RR2001", "COMMERCIAL", "5", "1000"),
              ("RR1003", "DOMESTIC", "1", "99980"), ("RR1004", "DOMESTIC", "2", "500")]:
        e.register_consumer(*c)
    e.add_reading("RR1001", "2026-07-28", "250", "")
    e.add_reading("RR2001", "2026-07-25", "1150", "0.85")
    e.add_reading("RR1003", "2026-07-22", "00012", "")
    e.add_reading("RR1004", "2026-07-20", "500", "")
    e.generate_bills("2026-07")
    e.record_payment("PAY-0001", "RR1001", "2026-07", "2026-08-13", "1270")
    e.add_reading("RR1001", "2026-08-28", "250", "")
    e.add_reading("RR2001", "2026-08-25", "1150", "0.90")
    e.generate_bills("2026-08")
    return e


EX = build_examples()
B1, B2, B3, B4 = (EX.bills[("RR1001", "2026-07")], EX.bills[("RR2001", "2026-07")],
                  EX.bills[("RR1003", "2026-07")], EX.bills[("RR1004", "2026-07")])
B1_AUG = EX.bills[("RR1001", "2026-08")]

# ----------------------------------------------------------------- document
story = []
story += [Spacer(1, 45 * mm), P("Domestic and Commercial Electricity<br/>Bill Engine with Slab Tariff and PF Penalty", TITLE),
          Spacer(1, 6 * mm), P("<b>Design Document</b> &nbsp;|&nbsp; ECE-023 &nbsp;|&nbsp; Capstone Project", SUB), Spacer(1, 10 * mm),
          table([["Team ID", "E035"], ["Section", "ECM B"],
                 ["Member 1", "Sayeeda Fathma Farooq - 1AT24UE069"], ["Member 2", "Sharvesh A K - 1AT24UE070"],
                 ["Domain", "Power & Energy - Distribution Billing"], ["Language", "Python 3.10+ (standard library only)"],
                 ["Repository", "E035-ECE-023"], ["Document version", "1.1 (updated to the official Week 2 sample data pack)"]],
                [45, 110], header=False),
          Spacer(1, 12 * mm),
          P("<i>Every business rule is registered as BR-nn, every validation as VR-nn. Section 11 maps each BR to its code and tests.</i>", SUB),
          PageBreak()]

# 1 ---------------------------------------------------------------
story += [P("1. Purpose and scope", H1),
          P("The engine turns monthly meter readings into bills for domestic and small commercial consumers of a BESCOM-style "
            "distribution company. It is driven by a command file (no UI). In scope: consumer registration, reading ingestion, "
            "monthly bill generation with line items, payment recording, late-payment interest carried to the next bill, and a monthly "
            "collection summary per category. Out of scope: GUI, database, real-time metering, HT/industrial tariffs, subsidies "
            "(stretch goal; the design leaves a hook - see section 12)."),
          P("<b>Success criterion (from the brief):</b> for the given consumer, reading and payment files, bills.csv and "
            "collection_summary.csv match the expected output field-for-field. Therefore: all money is <font face='Courier'>Decimal</font>, rounding "
            "is explicit and half-up, output formatting is deterministic, and diagnostics never pollute the result stream.")]

# 2 ---------------------------------------------------------------
story += [P("2. Business rule register", H1),
          P("BR-01 to BR-08 are the rules stated in the brief, in the brief's order. BR-09 to BR-14 are <b>derived rules</b>: the brief "
            "is silent or ambiguous, so the decision is explicit (reasoning in DECISION_LOG.md). The official sample data pack (Week 2) "
            "stated its conventions for these points; where the pack settles a rule, the engine follows the pack.")]
br = [["ID", "Rule", "Precise statement used by the engine"],
      ["BR-01", "Domestic slabs (telescopic)", "Units 1-50 @ Rs 4.75; 51-100 @ 7.00; 101-200 @ 8.25; above 200 @ 9.50. Each unit is priced by the slab it falls in."],
      ["BR-02", "Commercial slabs", "Units 1-100 @ Rs 9.00; above 100 @ 10.50 (also telescopic)."],
      ["BR-03", "Fixed charge", "Sanctioned kW x Rs 110 (DOMESTIC) or Rs 160 (COMMERCIAL), every month, even at 0 units."],
      ["BR-04", "PF penalty", "COMMERCIAL only. PF < 0.90: 1% of energy charge per full 0.01 below 0.90, cap 15%. PF >= 0.90: none. (PF 0.70 = 20 steps -> capped at 15%.)"],
      ["BR-05", "Electricity tax", "9% of (energy + fixed + PF penalty), rounded to 2 dp. Late interest and rounding are not taxed."],
      ["BR-06", "Meter rollover", "5-digit meter. closing >= opening: units = closing - opening. closing < opening: units = (99999 - opening) + closing + 1."],
      ["BR-07", "Late payment", "Due date = bill date + 15 days; a payment ON the due date is on time. Payment after the due date: interest = 1% x bill total x ceil(days late / 30), 2 dp, shown as the late-interest line of the consumer's FIRST bill dated strictly AFTER the payment date. Interest is not taxed."],
      ["BR-08", "Rounding", "Each line item 2 dp (half-up). Bill total rounded to nearest rupee (half-up); the difference is its own line item and may be negative."],
      ["BR-09", "Bill date and month", "Bill date = reading date; bill month = YYYY-MM of the reading date; at most one bill per consumer per month (pack convention)."],
      ["BR-10", "Opening reading chain", "Opening = meter_start_reading for the first bill, then the previous closing reading. Equal readings = zero units, not a rollover (pack convention)."],
      ["BR-11", "Late measure", "Each payment pays one bill in full. Days late = payment date - due date. 30 days = 1 period, 31 days = 2 periods."],
      ["BR-12", "Interest charged once", "A late payment's interest is placed on exactly one bill and never repeated. Base = total of the paid bill (including any interest that bill carried). Unpaid bills attract no interest."],
      ["BR-13", "Payment validation", "A payment must name an existing bill, must not pre-date the bill, must not exceed the outstanding amount, and needs a unique payment id; an amount different from the bill total is accepted with a WARN."],
      ["BR-14", "Collection summary", "Per bill month and category (DOMESTIC first): bills, units, billed, collected (any payment date), outstanding = billed - collected, late_payments = bills paid after due date, interest_billed = late-interest lines on that month's bills."],
      ["BR-15", "Output files", "bills.csv (one row per consumer per month, ordered by month then RR) and collection_summary.csv, in the exact column order of the pack; readings keep 5 digits; money as plain 2-dp decimals."]]
story += [table(br, [14, 34, 122])]

# 3 ---------------------------------------------------------------
story += [P("3. Domain model", H1),
          table([["Entity", "Key attributes", "Notes"],
                 ["Consumer", "rr (key), category, load_kw, start_reading; state: last_closing, last_reading_date, last_billed_month", "State advances only when a bill is generated successfully."],
                 ["Reading", "rr, reading_date, closing, pf", "Unique per (rr, month). PF mandatory for COMMERCIAL, ignored for DOMESTIC."],
                 ["Bill", "bill_id = rr-YYYY-MM, bill/due date, opening, closing, units, rollover flag, slab lines, energy, fixed, pf_penalty, tax, interest (+ per-bill detail), rounding, total", "Immutable once generated, except its payment ledger and interest_levied counter."],
                 ["Payment", "payment_id, rr, bill_month, pay_date, amount", "Attached to exactly one bill; held as pending if that bill does not exist yet."],
                 ["SlabLine", "from_unit, to_unit, units, rate, amount", "Printed on the bill so a customer (and the examiner) can audit the energy charge."]],
                [24, 90, 56]),
          Spacer(1, 3 * mm),
          P("Relationships: Consumer 1-N Reading (one per month); Consumer 1-N Bill (one per month); Bill 1-N Payment; Bill 1-N interest "
            "contributions to later bills of the same consumer.")]

# 4 ---------------------------------------------------------------
story += [P("4. Architecture", H1), arch_diagram(), Spacer(1, 2 * mm),
          P("<b>Design principles.</b> (1) Rules live in pure functions (tariff.py, interest.py) with no state or I/O, so each rule is unit-tested "
            "and can be explained alone. (2) All rates are in config.py - tariff changes touch one file. (3) Commands are thin: they parse and "
            "delegate to the engine. (4) A bad row or command never aborts a run: it is reported with file/line and skipped. "
            "(5) Results go to stdout, diagnostics to stderr, exit code 1 if any ERROR - so stdout can be diffed against the expected output.")]

# 5 ---------------------------------------------------------------
story += [P("5. Processing pipeline for one bill", H1),
          table([["Step", "Action", "Rule"],
                 ["1", "Locate the consumer's reading for the requested month; skip (WARN) if absent or already billed", "BR-09"],
                 ["2", "Check month is after the last billed month", "VR-15"],
                 ["3", "units = f(opening, closing) with rollover detection", "BR-06, BR-10"],
                 ["4", "Energy charge by telescopic slabs (slab lines retained)", "BR-01/02"],
                 ["5", "Fixed charge = kW x rate", "BR-03"],
                 ["6", "PF penalty (commercial) from energy charge and PF", "BR-04"],
                 ["7", "Tax = 9% x (energy + fixed + PF penalty)", "BR-05"],
                 ["8", "Late interest: every not-yet-charged late payment of this consumer's earlier bills dated before this bill date adds 1% x paid-bill total x periods", "BR-07/11/12"],
                 ["9", "gross = sum of lines; total = round-half-up to rupee; rounding = total - gross", "BR-08"],
                 ["10", "Commit: update consumer state, store bill, mark interest as levied, attach any pending payments", "-"]],
                [10, 135, 25])]

# 6 ---------------------------------------------------------------
story += [PageBreak(), P("6. Key algorithms", H1), P("6.1 Telescopic slabs", H2),
          P("<font face='Courier'>lower = 0; for each (upper, rate): if units &lt;= lower stop; top = min(units, upper); n = top - lower; "
            "amount = n x rate; lower = top</font>. Because <i>lower</i> advances slab by slab, each unit is priced exactly once at the rate of the slab it "
            "occupies. Boundary behaviour: 50 units stays entirely in slab 1 (Rs 237.50); 51 units adds exactly one unit at Rs 7.00 (Rs 244.50)."),
          P("6.2 Meter rollover", H2),
          P("If closing &lt; opening the meter has passed 99999 and restarted at 00000. The units are those from opening up to 99999 "
            "(<i>99999 - opening</i>), plus the step from 99999 to 00000 (<i>+1</i>), plus the new reading (<i>closing</i>). "
            "Example from the brief: opening 99980, closing 00012: 19 + 1 + 12 = <b>32 units</b>. Closing equal to opening is zero consumption, not a full wrap."),
          P("6.3 PF penalty", H2),
          P("steps = floor((0.90 - PF) / 0.01); penalty% = min(steps x 1%, 15%); penalty = energy x penalty%. All arithmetic in Decimal, so "
            "PF 0.89 is exactly one step (no floating-point 0.8999.. surprise). PF 0.90 gives zero steps; PF 0.70 gives 20 steps and is capped to 15%."),
          P("6.4 Late-payment interest", H2),
          P("Interest is driven by <b>late payments</b>, not by unpaid balances. For a payment made after its bill's due date: "
            "periods = ceil(days late / 30); interest = 1% x <i>total of the paid bill</i> x periods, rounded to 2 dp. The amount is placed on the "
            "consumer's <b>first bill whose bill date is strictly after the payment date</b> and is never charged again. It is not taxed. "
            "A bill that is still unpaid (for example an October bill when the data stops on 31 Oct) attracts no interest. "),
          table([["Payment of a Rs 1270 bill (due 12 Aug)", "Days late", "Periods", "Interest", "Charged on"],
                 ["12 Aug (on the due date)", "0", "0", "Rs 0.00", "-"],
                 ["13 Aug (one day after)", "1", "1", "Rs 12.70", "next bill dated after 13 Aug"],
                 ["11 Sep", "30", "1", "Rs 12.70", "next bill dated after 11 Sep"],
                 ["12 Sep", "31", "2", "Rs 25.40", "next bill dated after 12 Sep"],
                 ["Never paid", "-", "-", "Rs 0.00", "-"]],
                [60, 22, 20, 24, 44])]

# 7 ---------------------------------------------------------------
story += [P("7. Input formats and validation rules", H1),
          table([["File", "Header (case-insensitive)"],
                 ["consumers.csv", "rr_number, consumer_name, category, sanctioned_load_kw, meter_start_reading, area, mobile (extra columns ignored)"],
                 ["readings.csv", "rr_number, reading_date (YYYY-MM-DD), closing_reading (5 digits, leading zeros kept), avg_pf (NONE for DOMESTIC; 0.00 is legal for COMMERCIAL)"],
                 ["payments.csv", "payment_id, rr_number, bill_month (YYYY-MM), payment_date, amount_rs, mode"]], [30, 140]),
          Spacer(1, 3 * mm)]
vr = [["Code", "Rule", "Code", "Rule"],
      ["VR-01", "RR number like RR-BG-50108 (letters, digits, hyphens)", "VR-11", "Month is YYYY-MM"],
      ["VR-02", "Category is DOMESTIC or COMMERCIAL", "VR-12", "Payment amount > 0, max 2 dp"],
      ["VR-03", "Sanctioned load > 0, max 2 dp, finite", "VR-13", "RR number is registered"],
      ["VR-04", "Meter start reading: whole number, 0-99999", "VR-14", "One reading per consumer per month"],
      ["VR-05", "Reading date is a real calendar date", "VR-15", "Bill month after last billed month"],
      ["VR-06", "RR number not already registered", "VR-16", "Reading date after previous reading date"],
      ["VR-07", "Closing reading whole number, 0-99999", "VR-17", "Payment id unique"],
      ["VR-08", "PF mandatory for COMMERCIAL (NONE/blank rejected)", "VR-18", "Payment not before bill date"],
      ["VR-09", "PF in [0, 1]", "VR-19", "Payment <= outstanding amount"],
      ["VR-10", "Payment / as-of date is a real date", "VR-20", "Required CSV columns present"],
      ["CMD-01", "Command is known", "CMD-02", "Correct argument count"]]
story += [table(vr, [16, 69, 16, 69])]

# 8 ---------------------------------------------------------------
story += [P("8. Edge cases mapped to evidence", H1),
          table([["Edge case (brief + pack)", "Handling", "Automated test", "Pack location"],
                 ["50 / 100 / 200 units; 201", "Telescopic loop; boundary stays in lower slab", "test_exactly_50/100/200_units, test_201_units", "readings lines 6, 59, 95; 53"],
                 ["PF exactly 0.90", "0 steps -> no penalty", "test_pf_exactly_090_no_penalty", "line 97 RR-BK-21066"],
                 ["PF 0.70 (cap)", "20 steps -> capped at 15%", "test_pf_070_cap_15_percent (1647.00)", "line 13 RR-JP-78161"],
                 ["PF 0.89", "1 step = 1%", "test_pf_089_one_percent", "line 2 RR-BG-50108"],
                 ["Rollover 99980 -> 00012 (+ second)", "(99999-99980)+12+1 = 32; 99731 -> 00285 = 554", "test_rollover_99980_to_00012, test_second_rollover", "lines 75, 92"],
                 ["Zero-consumption months (4)", "Energy 0; fixed + tax still billed; PF 0.00 accepted", "test_zero_consumption_months", "lines 10, 29, 52, 118"],
                 ["Paid on due date vs one day late", "0 days vs 1 day late", "test_pay_0035..., test_pay_0036...", "payments lines 36, 37"],
                 ["Other late payments (30 / 31 / 44 days)", "ceil(days/30) periods; lands on first later bill", "test_pay_0070, 0078, 0080, 0079", "payments lines 71, 79, 81, 80"],
                 ["Rounding at exactly 50 paise", "Half-up -> +0.50", "test_rounding_exactly_50_paise_half_up", "line 66 RR-JP-94514"],
                 ["Fractional load; unpaid October bills", "kW x rate; outstanding, no interest", "test_fractional_load, test_unpaid_october...", "-"]],
                [40, 46, 48, 36])]

# 9 ---------------------------------------------------------------
story += [PageBreak(), P("9. Worked bills (hand-verifiable)", H1),
          P("These are the bills the engine prints for the inputs below; every figure can be reproduced with a calculator."),
          P("9.1 Domestic, 3 kW, opening 00120 -> closing 00250 (130 units)", H2),
          table([["Step", "Working", "Result"],
                 ["Units", "250 - 120", "130"],
                 ["Slab 1", "50 x 4.75", fmt(D(50) * D("4.75"))],
                 ["Slab 2", "50 x 7.00", fmt(D(50) * D("7.00"))],
                 ["Slab 3", "30 x 8.25", fmt(D(30) * D("8.25"))],
                 ["Energy charge", "237.50 + 350.00 + 247.50", fmt(B1.energy)],
                 ["Fixed charge", "3 kW x 110", fmt(B1.fixed)],
                 ["Tax", "9% x (835.00 + 330.00 + 0.00) = 104.85", fmt(B1.tax)],
                 ["Gross", "835.00 + 330.00 + 0.00 + 104.85", fmt(B1.energy + B1.fixed + B1.tax)],
                 ["Rounding line", "1270 - 1269.85", fmt(B1.rounding)],
                 ["<b>Total payable</b>", "nearest rupee", "<b>Rs %s</b>" % B1.total]], [35, 100, 35]),
          Spacer(1, 3 * mm),
          P("<b>Telescopic vs flat.</b> A <i>flat</i> slab prices all 130 units at the rate of the slab the total lands in (Rs 8.25): "
            "130 x 8.25 = Rs %s. <i>Telescopic</i> prices only the units above each threshold at the higher rate: Rs %s. "
            "The telescopic method has no cliff - going from 100 to 101 units adds only Rs 8.25 (Rs 587.50 -> Rs 595.75), whereas a flat scheme "
            "would suddenly re-price all 101 units at 8.25 (Rs 833.25). That is why consumption exactly at a boundary is a named edge case."
            % (fmt(D(130) * D("8.25")), fmt(B1.energy))),
          P("9.2 Commercial, 5 kW, 150 units, average PF 0.85", H2),
          table([["Step", "Working", "Result"],
                 ["Energy", "100 x 9.00 + 50 x 10.50 = 900.00 + 525.00", fmt(B2.energy)],
                 ["Fixed", "5 kW x 160", fmt(B2.fixed)],
                 ["PF penalty", "0.90 - 0.85 = 5 steps -> 5% x 1425.00", fmt(B2.pf_penalty)],
                 ["Tax", "9% x (1425.00 + 800.00 + 71.25) = 206.6625", fmt(B2.tax)],
                 ["Gross / rounding", "2502.91 -> 2503", f"{fmt(B2.rounding)}"],
                 ["<b>Total payable</b>", "", "<b>Rs %s</b>" % B2.total]], [35, 100, 35]),
          P("9.3 Rollover and zero-consumption", H2),
          table([["Case", "Working", "Energy / Fixed / Tax", "Total"],
                 ["Domestic 1 kW, 99980 -> 00012", "units = 19 + 12 + 1 = 32; 32 x 4.75", f"{fmt(B3.energy)} / {fmt(B3.fixed)} / {fmt(B3.tax)}", f"Rs {B3.total}"],
                 ["Domestic 2 kW, 500 -> 500", "0 units; fixed 2 x 110; tax 9% x 220.00", f"{fmt(B4.energy)} / {fmt(B4.fixed)} / {fmt(B4.tax)}", f"Rs {B4.total}"]],
                [42, 62, 42, 24]),
          P("9.4 Late interest carried to the next bill", H2),
          P("The Rs %s bill of 28 Jul 2026 (due 12 Aug) is paid on 13 Aug: 1 day late = 1 period, so interest = 1%% x %s = "
            "<b>Rs %s</b>. The first bill dated after 13 Aug is the 28 Aug bill, which therefore shows: energy %s + fixed %s + PF 0.00 + tax %s + interest %s, rounded -> "
            "<b>Rs %s</b> (interest is not taxed)." % (B1.total, B1.total, fmt(B1_AUG.interest), fmt(B1_AUG.energy), fmt(B1_AUG.fixed), fmt(B1_AUG.tax),
                               fmt(B1_AUG.interest), B1_AUG.total)),
          Spacer(1, 2 * mm),
          KeepTogether([P("Printed bill (July, domestic 130 units):", SMALL), Preformatted(format_bill(B1), MONO)])]

# 10 --------------------------------------------------------------
story += [PageBreak(), P("10. Test strategy", H1),
          table([["Layer", "What it proves", "Where"],
                 ["Unit - rules", "Each BR in isolation incl. every boundary (0,1,50,51,100,101,200,201), PF 0.89/0.895/0.90/0.75/0.70, rollover variants, half-up rounding", "tests/test_tariff.py"],
                 ["Unit - validation", "Every VR code is reachable and rejects bad input; NONE / 0.00 PF handling", "tests/test_validation.py"],
                 ["Engine", "Bill assembly, reading chain, late-interest rules (on due date, +1, +30, +31 days, lands after payment date, charged once, untaxed), payment validation, summary", "tests/test_engine.py"],
                 ["Official pack", "Every planted scenario by README line number; 120 bills vs independent oracle; all 108 pack payments equal engine totals; CSV formats; golden snapshots; second independent implementation (standalone/) gives byte-identical files; bad-input robustness", "tests/test_end_to_end.py"]],
                [28, 106, 36]),
          P("Run: <font face='Courier'>python -m unittest discover -s tests -t .</font> (no third-party packages). "
            "Invariants asserted on every bill: lines add up to the total; total is a whole rupee; |rounding| &lt;= 0.50; "
            "summary billed = sum of bills; collected + outstanding = billed. Strongest evidence: the pack's payment amounts were generated from the official totals, and all 108 equal our computed totals.")]

# 11 --------------------------------------------------------------
story += [P("11. Traceability: business rule to code to tests", H1),
          table([["Rule", "Implementation", "Tests"],
                 ["BR-01/02", "tariff.energy_charge, config.SLABS", "TestDomesticSlabs, TestCommercialSlabs"],
                 ["BR-03", "tariff.fixed_charge", "TestFixedCharge, test_zero_consumption_month"],
                 ["BR-04", "tariff.pf_penalty", "TestPFPenalty, test_commercial_pf_070_cap"],
                 ["BR-05", "tariff.electricity_tax", "TestTax"],
                 ["BR-06", "tariff.units_consumed", "TestRollover, test_rollover_month_from_brief"],
                 ["BR-07/11/12", "interest.periods_overdue / interest_for_payment; engine._bill_one", "TestLateInterest (10 tests), test_pay_0035..0080"],
                 ["BR-08", "money.q2 / round_rupee; engine._bill_one", "TestRounding, test_line_items_always_reconcile_to_total"],
                 ["BR-09/10", "engine._bill_one, Consumer state", "test_reading_chain_uses_previous_closing, test_rebilling_month_is_idempotent"],
                 ["BR-13", "engine.record_payment / _attach", "TestPaymentValidation"],
                 ["BR-14/15", "engine.collection_summary, outputs.py", "TestSummary, TestPackOutputFiles"]],
                [26, 80, 64])]

# 12 --------------------------------------------------------------
story += [P("12. Assumptions, risks and extension points", H1),
          P("<b>Resolved by the official pack.</b> Bill date = reading date; PF steps are whole 0.01 steps; late interest = 1% x bill total x ceil(days late/30) on the "
            "first bill dated after the payment; summary definitions; output file formats. <b>Still our own decisions</b> (pack silent): payments that pre-date their bill or exceed "
            "its total are rejected, a differing amount only warns; a consumer with no reading in a month gets no bill and no fixed charge; bad rows are skipped and reported."),
          P("<b>Risk: hidden month.</b> The third month's expected output is hidden, so correctness must come from rule fidelity, not from fitting visible "
            "data. Mitigations: independent oracle test, a second independent implementation, boundary tests, every ambiguity written down before coding."),
          P("<b>Extension points (stretch goals).</b> Subsidy for consumers under 40 units: add a rule function between energy charge and tax and a "
            "line item in Bill/report. Arrears ageing 30/60/90: read-only report over Bill.outstanding and due_date - no change to billing logic."),
          P("<b>Limitations.</b> A closing reading lower than opening is always treated as rollover (a meter replacement or data-entry error is indistinguishable); "
            "such bills carry an explicit rollover note so a human can review them.")]

# ----------------------------------------------------------------- footer + build
def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.grey)
    canvas.drawString(18 * mm, 10 * mm, "E035 - ECE-023 - Electricity Bill Engine - Design Document v1.1")
    canvas.drawRightString(192 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


out = os.path.join(ROOT, "docs", "design_document.pdf")
doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                        title="E035 ECE-023 Design Document", author="Team E035")
doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=footer)
print("wrote", out)
