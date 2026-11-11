"""Pure tariff functions: no state, no I/O - one function per business rule,
so each rule can be unit-tested and explained in isolation."""
from decimal import Decimal, ROUND_FLOOR
from typing import List, Optional, Tuple

from . import config as cfg
from .models import SlabLine
from .money import q2


def units_consumed(opening: int, closing: int) -> Tuple[int, bool]:
    """BR-06. Returns (units, rollover?).

    closing < opening  -> the 5-digit meter wrapped past 99999:
        units = (99999 - opening) + closing + 1
    closing >= opening -> units = closing - opening   (equal => zero units)
    """
    if closing >= opening:
        return closing - opening, False
    return (cfg.METER_MAX - opening) + closing + 1, True


def energy_charge(category: str, units: int) -> Tuple[Decimal, List[SlabLine]]:
    """BR-01 / BR-02. Telescopic: each unit is priced by the slab it falls in,
    NOT by the slab the total lands in."""
    lower = 0                       # units already priced by earlier slabs
    total = Decimal("0.00")
    lines: List[SlabLine] = []
    for upper, rate in cfg.SLABS[category]:
        if units <= lower:
            break
        top = units if upper is None else min(units, upper)
        n = top - lower
        amount = q2(n * rate)
        lines.append(SlabLine(lower + 1, top, n, rate, amount))
        total += amount
        lower = top
    return q2(total), lines


def fixed_charge(category: str, load_kw: Decimal) -> Decimal:
    """BR-03. Charged every month, even at zero consumption."""
    return q2(load_kw * cfg.FIXED_RATE_PER_KW[category])


def pf_penalty(category: str, energy: Decimal, pf: Optional[Decimal]) -> Tuple[Decimal, Decimal]:
    """BR-04. Returns (penalty amount, penalty fraction of energy charge).

    COMMERCIAL only. For every FULL 0.01 that PF is below 0.90 add 1% of the
    energy charge, capped at 15%. PF == 0.90 (or better) -> no penalty.
    """
    if category != cfg.COMMERCIAL or pf is None or pf >= cfg.PF_THRESHOLD:
        return Decimal("0.00"), Decimal("0")
    steps = int(((cfg.PF_THRESHOLD - pf) / cfg.PF_STEP).to_integral_value(rounding=ROUND_FLOOR))
    pct = min(steps * cfg.PF_PENALTY_PER_STEP, cfg.PF_PENALTY_CAP)
    return q2(energy * pct), pct


def electricity_tax(energy: Decimal, fixed: Decimal, penalty: Decimal) -> Decimal:
    """BR-05. 9% on energy + fixed + PF penalty (NOT on late interest)."""
    return q2((energy + fixed + penalty) * cfg.TAX_RATE)
