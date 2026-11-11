# ECE-023 – Domestic and Commercial Electricity Bill Engine with Slab Tariff and PF Penalty — Sample Data Pack
Prepared by 10 SECONDS for Team E035.

This pack is the input for a BESCOM-style billing engine: 40 consumers (28 domestic, 12 commercial), three monthly meter readings each (August, September and October 2026), and the payments received up to 2026-10-31. Your engine reads `commands.txt`, generates one bill per consumer per month with every line item, and prints a monthly collection summary per category.

Pack conventions where the brief is silent: the bill month is the month of the reading date and the bill date is the reading date; the opening reading of the first bill is meter_start_reading, after that the previous closing reading. Due date = bill date + 15 days; a payment dated on the due date is on time. Each payment pays one bill in full. For a late payment, interest = 1% × bill total × ceil(days late / 30), rounded to 2 decimals, and it appears as the `late_interest` line on the consumer's first bill whose bill date is AFTER the payment date (interest is not taxed). PF penalty steps = (0.90 − avg_pf) / 0.01 (whole steps; avg_pf has 2 decimals). All money rounding is half up (2 decimals for line items, nearest rupee for the total).

## Files
| File | What it holds | Rows |
|---|---|---|
| consumers.csv | Consumers with category, sanctioned load and meter start reading | 40 |
| readings.csv | Monthly meter readings (Aug–Oct 2026) | 120 |
| payments.csv | Payments received against bills | 108 |
| commands.txt | Load commands, bill generation per month, collection summaries | 9 |

## Column reference
Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals (no commas, no symbol); percentages as plain numbers (12.5 = 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix.

### consumers.csv
| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| rr_number | string | RR-XX-nnnnn | unique | Primary key |
| consumer_name | string | - |  | Person (domestic) or business (commercial) |
| category | string | - | DOMESTIC, COMMERCIAL | Picks the slab table and fixed-charge rate |
| sanctioned_load_kw | decimal | kW, 1 dp |  | Fixed charge = Rs 110 / Rs 160 × kW |
| meter_start_reading | string | 5 digits with leading zeros | 00000–99999 | Opening reading of the August bill |
| area | string | - |  | Not used by any rule |
| mobile | string | 10 digits | starts 6–9 | Not used by any rule |

### readings.csv
| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| rr_number | string | RR-XX-nnnnn | must exist in consumers.csv |  |
| reading_date | date | YYYY-MM-DD | 2026-08-02 … 2026-10-06 | Becomes the bill date |
| closing_reading | string | 5 digits with leading zeros | 00000–99999 | Lower than the opening reading = meter rollover |
| avg_pf | decimal or NONE | 2 dp | 0.00–1.00 | NONE for domestic consumers |

### payments.csv
| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| payment_id | string | PAY-nnnn | unique | In payment-date order |
| rr_number | string | RR-XX-nnnnn | must exist in consumers.csv |  |
| bill_month | string | YYYY-MM | 2026-08, 2026-09, 2026-10 | The bill being paid |
| payment_date | date | YYYY-MM-DD |  | Late when after the due date |
| amount_rs | decimal | Rs, 2 dp |  | Equals the bill total |
| mode | string | - | UPI, BBPS, CASH_COUNTER, NET_BANKING | Not used by any rule |

## Command file format
`commands.txt` holds one command per line as `COMMAND_NAME|arg1|arg2|...`. Commands must be processed in file order, top to bottom. Lines starting with `#` are comments and blank lines are ignored.

| Command | Arguments (in order) | Meaning |
|---|---|---|
| LOAD_CONSUMERS / LOAD_READINGS / LOAD_PAYMENTS | file | Load the three input files |
| GENERATE_BILLS | YYYY-MM | Generate and print the bills of that month (run months in order) |
| COLLECTION_SUMMARY | YYYY-MM | Print the collection summary of that bill month per category |

`bill_id` is BL-YYYYMM-<rr_number> (for example BL-202608-RR-JN-12345). Readings in bills.csv keep the 5-digit form. `rounding_rs` may be negative. In the summary, `collected_rs` is the sum of payments against that month's bills (any payment date in the file), `outstanding_rs` = billed − collected, `late_payments` counts that month's bills paid after their due date, and `interest_billed_rs` is the late-interest lines on that month's bills.

## Planted scenarios
Line numbers count the header row as line 1, so the first data row of a CSV is line 2. For commands.txt the line number is the physical line in the file (comment lines included).

- **Consumption of exactly 50, 100 and 200 units (slab boundaries)** — Domestic consumption of exactly 50 units at readings.csv line 6 (RR-BT-62186, 2026-08, 58444 → 58494), 100 units at readings.csv line 59 (RR-BK-83373, 2026-09, 12952 → 13052) and 200 units at readings.csv line 95 (RR-JN-10028, 2026-10, 55310 → 55510) — each ends exactly on a slab edge, so no unit is billed at the next rate. Compare 201 units at readings.csv line 53 (RR-JP-10672, 2026-09, 89227 → 89428) (one unit at Rs 9.50).
- **Commercial consumer with PF exactly 0.90 (no penalty) and with PF 0.70 (cap applies)** — Commercial PF exactly 0.90 at readings.csv line 97 (RR-BK-21066, 2026-10, 55056 → 56116) → no penalty; PF 0.70 at readings.csv line 13 (RR-JP-78161, 2026-08, 72642 → 73702) → 20 steps of 0.01 = 20%, capped at 15% of the energy charge. Also PF 0.89 at readings.csv line 2 (RR-BG-50108, 2026-08, 67884 → 68316) → 1%.
- **Meter rollover month where closing reading 00012 follows opening reading 99980** — readings.csv line 75 (RR-BT-62684, 2026-09, 99980 → 00012): opening 99980, closing 00012 → (99999 − 99980) + 12 + 1 = 32 units. A second rollover: readings.csv line 92 (RR-BK-69000, 2026-10, 99731 → 00285).
- **Zero consumption month (fixed charge and tax still apply)** — Zero-consumption months (closing = opening): readings.csv line 10 (RR-BK-70433, 2026-08, 50638 → 50638), readings.csv line 29 (RR-BG-75333, 2026-08, 42627 → 42627), readings.csv line 52 (RR-JN-75217, 2026-09, 29746 → 29746), readings.csv line 118 (RR-JN-75217, 2026-10, 29746 → 29746) — fixed charge and 9% tax on it are still billed (the commercial one reports avg_pf 0.00 with no load; PF penalty is 1% of a zero energy charge = 0.00).
- **Payment made exactly on the due date versus one day after** — payments.csv line 36 (PAY-0035, RR-BT-99048 bill 2026-08, bill date 2026-08-04, due 2026-08-19, paid 2026-08-19) is paid exactly on the due date → not late, no interest. payments.csv line 37 (PAY-0036, RR-JN-24514 bill 2026-08, bill date 2026-08-06, due 2026-08-21, paid 2026-08-22) is paid one day after → 1 period × 1% interest on the next bill.

Extra traps (realistic things your validation should catch):

- **Other late payments (six late in total)** — payments.csv line 38 (PAY-0037, RR-BT-61171 bill 2026-08, bill date 2026-08-06, due 2026-08-21, paid 2026-09-02) (12 days late), payments.csv line 71 (PAY-0070, RR-BK-51504 bill 2026-08, bill date 2026-08-03, due 2026-08-18, paid 2026-09-17) (exactly 30 days → still 1 period), payments.csv line 79 (PAY-0078, RR-BG-72393 bill 2026-08, bill date 2026-08-06, due 2026-08-21, paid 2026-09-21) (31 days → 2 periods), payments.csv line 81 (PAY-0080, RR-JN-61032 bill 2026-08, bill date 2026-08-03, due 2026-08-18, paid 2026-10-01) (44 days → 2 periods; paid before that consumer's October reading, so the interest goes on the October bill) and payments.csv line 80 (PAY-0079, RR-BT-77012 bill 2026-09, bill date 2026-09-06, due 2026-09-21, paid 2026-09-30). Interest goes on the first bill dated after the payment date.
- **Rounding exactly at 50 paise** — readings.csv line 66 (RR-JP-94514, 2026-09, 15717 → 15894): this bill's subtotal ends in exactly .50 → round half up to the next rupee (rounding line +0.50).
- **Fractional sanctioned load** — Some consumers have 1.5 or 2.5 kW (or 7.5 kW commercial); fixed charge = rate × kW, e.g. 2.5 kW domestic = Rs 275.00.
- **Unpaid October bills** — Not every October bill has a payment yet (the data stops on 2026-10-31); they count as outstanding in the summary and attract no interest in this pack.

## What is NOT in this pack
Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-08). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation
Produce these files (CSV, header row, same conventions as above). Column order matters.

### bills.csv
One row per consumer per month, ordered by bill_month then rr_number.

Columns in order: `bill_id`, `rr_number`, `category`, `bill_month`, `bill_date`, `due_date`, `opening_reading`, `closing_reading`, `units`, `energy_charge_rs`, `fixed_charge_rs`, `pf_penalty_rs`, `tax_rs`, `late_interest_rs`, `rounding_rs`, `total_rs`

### collection_summary.csv
One row per bill month per category (DOMESTIC first).

Columns in order: `bill_month`, `category`, `bills`, `units`, `billed_rs`, `collected_rs`, `outstanding_rs`, `late_payments`, `interest_billed_rs`
