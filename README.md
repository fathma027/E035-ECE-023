# E035-ECE-023 - Domestic and Commercial Electricity Bill Engine

**Team E035 (ECM B)** - Sayeeda Fathma Farooq (1AT24UE069), Sharvesh A K (1AT24UE070)
**Language:** Python 3.10+ - standard library only (no `pip install` to run or test)

A command-file-driven billing engine in the style of a BESCOM distribution company: telescopic energy slabs, fixed charge per kW,
commercial power-factor penalty, electricity tax, meter rollover, late-payment interest and a monthly collection summary.
Built and verified against the official 10 SECONDS sample data pack (`data/`).

## Quick start

```bash
python main.py data/commands.txt              # writes output/bills.csv + output/collection_summary.csv
python main.py data/commands.txt myout/       # choose the output folder
python -m unittest discover -s tests -t .     # run the 120 tests
```

* **Evaluation files:** `bills.csv` and `collection_summary.csv`, exact columns/order from the pack README (see `billing/outputs.py`).
* **stdout:** readable bills and summaries. **stderr:** `INFO` / `WARN` / `ERROR` lines (with file + line numbers).
* **Exit code:** `0` clean, `1` at least one rejected row/command, `2` usage/fatal error.
* `standalone/billing_engine.py` is an independent single-file implementation (`python standalone/billing_engine.py data out/`);
  a test proves both produce byte-identical files.

## Command file (pipe-separated, processed top to bottom, `#` comments)

| Command | Meaning |
|---|---|
| `LOAD_CONSUMERS\|consumers.csv` / `LOAD_READINGS\|readings.csv` / `LOAD_PAYMENTS\|payments.csv` | Load inputs (paths relative to the command file) |
| `GENERATE_BILLS\|YYYY-MM` | Generate + print that month's bills (run months in order); rewrites `bills.csv` |
| `COLLECTION_SUMMARY\|YYYY-MM` | Print the per-category summary; rewrites `collection_summary.csv` |
| `REGISTER\|rr\|category\|kw\|start`, `PAYMENT\|id\|rr\|YYYY-MM\|date\|amount` | Single-record extras |

## Business rules (BR-01..BR-15; full statements in `docs/design_document.pdf`)

| ID | Rule |
|---|---|
| BR-01 | Domestic telescopic slabs: 50 @ 4.75, 51-100 @ 7.00, 101-200 @ 8.25, >200 @ 9.50 |
| BR-02 | Commercial slabs: 100 @ 9.00, >100 @ 10.50 |
| BR-03 | Fixed charge Rs 110/kW (domestic), Rs 160/kW (commercial), every month incl. zero consumption |
| BR-04 | Commercial PF < 0.90: +1% of energy per whole 0.01 below, capped at 15% |
| BR-05 | Tax 9% on energy + fixed + PF penalty (interest not taxed) |
| BR-06 | 5-digit meter rollover: units = (99999 - opening) + closing + 1 when closing < opening |
| BR-07 | Due = bill date + 15; paid on due date = on time. Late payment: interest = 1% x bill total x ceil(days late/30), on the consumer's first bill dated AFTER the payment date |
| BR-08 | Line items 2 dp half-up; total to nearest rupee; rounding difference is a line item (may be negative) |
| BR-09..15 | Bill date = reading date, opening-reading chain, late measure, interest charged once, payment validation, summary definition, output files |

All rates are in `billing/config.py`.

## Layout

```
main.py                    entry point
billing/                   config, money, models, validation, tariff, interest, engine, io_files, commands, outputs, report
standalone/billing_engine.py   independent single-file engine (cross-check)
data/                      OFFICIAL sample pack: consumers/readings/payments CSV, commands.txt, PACK_README.md
expected/                  snapshot of our output on the sample pack (regression guard - NOT official expected output)
tests/                     120 tests (rules, validation, engine, every planted pack scenario, output formats)
tools/build_design_doc.py  regenerates the design PDF (needs reportlab)
docs/                      design_document.pdf, viva_prep.md
DECISION_LOG.md
```

## Verification

* Every planted scenario in the pack README is a named test (by line number): slab boundaries 50/100/200/201, PF 0.90/0.89/0.70 cap, both rollovers,
  four zero-consumption months, due-date vs +1 day, 30/31/44-day late payments, the 50-paise rounding case, fractional load, unpaid October bills.
* All 120 bills match an independently written closed-form oracle.
* **All 108 payment amounts in the pack equal the totals our engine computes** (the pack generated them from the official totals), including bills that carry interest.
* Second implementation (`standalone/`) gives byte-identical `bills.csv` and `collection_summary.csv`.

## Submission checklist

- [x] Source code, README, design document PDF, test suite, decision log
- [ ] 5-minute demo video link: `<add link>` (script in `docs/viva_prep.md`)
- [ ] Repo `E035-ECE-023` shared with support@10seconds.co.in; final email subject "E035 - Final Submission"

Not implemented (stretch): subsidy under 40 units, 30/60/90 arrears ageing (extension points in the design document).
