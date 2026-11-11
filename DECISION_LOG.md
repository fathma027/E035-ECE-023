# Decision Log - Team E035 / ECE-023

Format: Context -> Decision -> Why -> Impact. **[PACK]** = settled by the official sample data pack (Week 2); these replaced our earlier assumptions.

### DL-01 Python, standard library only
Zero install friction. Only the design-document builder needs `reportlab`.

### DL-02 Decimal, never float; half-up rounding
Output is compared field-for-field. All money is `Decimal`, `ROUND_HALF_UP` (not Python's banker's `round()`): 206.6625 -> 206.66, subtotal ending .50 -> +0.50 rounding.

### DL-03 Bill date = reading date; due date = +15 days **[PACK]**
Bill month = month of the reading date. One bill per consumer per month; months generated in order.

### DL-04 Opening reading **[PACK]**
First bill: `meter_start_reading`; afterwards the previous closing. `closing == opening` = 0 units (not a wrap); `closing < opening` = rollover.
Limitation: a meter replacement or typo looks like a rollover; the printed bill flags rollovers.

### DL-05 PF penalty = whole 0.01 steps **[PACK]**
`floor((0.90 - pf)/0.01)`, cap 15%. Decimal arithmetic makes 0.89 exactly one step. PF `0.00` is legal for a zero-consumption commercial month (penalty on 0 energy = 0.00).
Domestic PF is `NONE` and ignored; a commercial row with `NONE`/blank is rejected (VR-08) rather than silently waiving a penalty.

### DL-06 Late interest model **[PACK] - replaces our earlier "overdue balance" model**
Earlier we modelled interest on unpaid balances up to the next bill. The pack defines it per *late payment*: interest = 1% x bill total x ceil(days late/30), placed on the
consumer's first bill dated strictly after the payment date, untaxed; payment on the due date is on time; unpaid bills attract no interest.
The base is the paid bill's total as printed (including any interest it carries) - confirmed by the pack: all 108 payment amounts equal our totals, incl. interest-bearing bills.
Each payment's interest is charged exactly once.

### DL-07 Payment validation (pack silent - our decision)
Rejected: unknown consumer, amount <= 0 / > 2 dp, duplicate payment id, dated before its bill, exceeding the outstanding amount. An amount different from the bill total is recorded with a WARN.
Payments for bills not yet generated are held and applied on generation; unmatched ones are reported at the end.

### DL-08 Collection summary **[PACK]**
`collected` = all payments against that month's bills (any date); `outstanding` = billed - collected; `late_payments` = that month's bills paid after due date;
`interest_billed` = late-interest lines printed on that month's bills. Rows ordered by month then DOMESTIC, COMMERCIAL.

### DL-09 Output files **[PACK]**
`bills.csv`, `collection_summary.csv`, exact column order, 5-digit readings, plain 2-dp money (total as e.g. `1291.00`), `bill_id = BL-YYYYMM-<rr>`.
Default output folder `./output` (second CLI argument overrides). Rewritten after each GENERATE_BILLS / COLLECTION_SUMMARY so a partial run still leaves valid files.

### DL-10 Command format **[PACK]**
`COMMAND|arg|...`; `#` comment lines; blank lines ignored; processed in order. Unknown command or missing argument -> ERROR on stderr, run continues.

### DL-11 Error policy
Bad rows/commands never abort a run: ERROR with file + line on stderr, row skipped, exit code 1. Results (stdout, CSV) stay clean.

### DL-12 Missing reading
No reading for a consumer in a month: WARN, no bill, no fixed charge. A multi-month gap is billed as one period with a WARN.

### DL-13 Two implementations
`standalone/billing_engine.py` is a separate single-file engine. A test requires byte-identical output - a cheap defence against a hidden-set surprise.
The version originally supplied for review used placeholder slab rates (domestic 4.15/5.60/7.15, three commercial slabs), floats, `round()` for PF steps, interest on the pre-interest total
and an un-padded `total_rs`; it produced negative outstanding amounts. All corrected.

### DL-14 Stretch goals deferred
Subsidy (<40 units) and 30/60/90 ageing are out of v1; extension points documented.
