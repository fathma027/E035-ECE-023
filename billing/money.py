"""Decimal helpers. All money is Decimal - never float (BR-08)."""
from decimal import Decimal, ROUND_HALF_UP

_TWO = Decimal("0.01")
_ONE = Decimal("1")


def D(value) -> Decimal:
    """Build a Decimal from str/int/Decimal (floats are routed via str)."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


def q2(value) -> Decimal:
    """Round half-up to 2 decimals - the precision of every line item (BR-08)."""
    return D(value).quantize(_TWO, rounding=ROUND_HALF_UP)


def round_rupee(value) -> Decimal:
    """Round half-up to the nearest whole rupee (BR-08)."""
    return D(value).quantize(_ONE, rounding=ROUND_HALF_UP)


def fmt(value) -> str:
    """Plain 2-decimal text, no thousands separator (stable for diffing)."""
    return f"{q2(value):.2f}"
