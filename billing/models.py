"""Plain data classes for the billing domain."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple


@dataclass
class Consumer:
    rr: str
    category: str
    load_kw: Decimal
    start_reading: int
    # Billing state - advanced only when a bill is successfully generated.
    last_closing: int = field(init=False)
    last_reading_date: Optional[date] = None
    last_billed_month: Optional[str] = None

    def __post_init__(self):
        self.last_closing = self.start_reading


@dataclass(frozen=True)
class Reading:
    rr: str
    reading_date: date
    closing: int
    pf: Optional[Decimal]

    @property
    def month(self) -> str:
        return self.reading_date.strftime("%Y-%m")


@dataclass(frozen=True)
class Payment:
    payment_id: str
    rr: str
    bill_month: str
    pay_date: date
    amount: Decimal


@dataclass(frozen=True)
class SlabLine:
    from_unit: int
    to_unit: int
    units: int
    rate: Decimal
    amount: Decimal


@dataclass
class Bill:
    rr: str
    category: str
    month: str
    bill_date: date
    due_date: date
    load_kw: Decimal
    opening: int
    closing: int
    units: int
    rollover: bool
    pf: Optional[Decimal]
    slabs: List[SlabLine]
    energy: Decimal
    fixed: Decimal
    pf_pct: Decimal            # fraction, e.g. 0.05
    pf_penalty: Decimal
    tax: Decimal
    interest: Decimal
    interest_detail: List[Tuple[str, str, Decimal]]   # (payment id, paid bill month, amount)
    rounding: Decimal
    total: Decimal
    # --- mutable ledger state ---
    payments: List[Payment] = field(default_factory=list)

    @property
    def bill_id(self) -> str:
        return f"{self.rr}-{self.month}"

    @property
    def paid(self) -> Decimal:
        return sum((p.amount for p in self.payments), Decimal("0.00"))

    @property
    def outstanding(self) -> Decimal:
        return self.total - self.paid
