"""Tariff and policy constants. Every value is tagged with its business rule.

Changing a tariff means changing ONLY this file - no rate is hard-coded
anywhere else in the engine.
"""
from decimal import Decimal

DOMESTIC = "DOMESTIC"
COMMERCIAL = "COMMERCIAL"
CATEGORIES = (DOMESTIC, COMMERCIAL)

# BR-01 / BR-02: telescopic slabs as (upper bound of slab in units, Rs/unit).
# upper=None means "all remaining units".
DOMESTIC_SLABS = [(50, Decimal("4.75")), (100, Decimal("7.00")),
                  (200, Decimal("8.25")), (None, Decimal("9.50"))]
COMMERCIAL_SLABS = [(100, Decimal("9.00")), (None, Decimal("10.50"))]
SLABS = {DOMESTIC: DOMESTIC_SLABS, COMMERCIAL: COMMERCIAL_SLABS}

# BR-03: fixed charge, Rs per kW of sanctioned load per month.
FIXED_RATE_PER_KW = {DOMESTIC: Decimal("110"), COMMERCIAL: Decimal("160")}

# BR-04: power-factor penalty (COMMERCIAL only).
PF_THRESHOLD = Decimal("0.90")
PF_STEP = Decimal("0.01")            # every full 0.01 below the threshold ...
PF_PENALTY_PER_STEP = Decimal("0.01")  # ... adds 1% of the energy charge
PF_PENALTY_CAP = Decimal("0.15")     # ... capped at 15%

# BR-05: electricity tax on (energy + fixed + PF penalty).
TAX_RATE = Decimal("0.09")

# BR-06: 5-digit meter.
METER_MAX = 99999

# BR-07: due date and late-payment interest.
DUE_DAYS = 15
LATE_PERIOD_DAYS = 30
LATE_RATE_PER_PERIOD = Decimal("0.01")
