"""Field-level parsing and validation. Every parser raises ValidationError
with a stable code so that tests and logs can refer to rules (VR-xx)."""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .config import CATEGORIES, METER_MAX


class ValidationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


_RR_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{3,19}$")
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _dec(text: str, code: str, what: str) -> Decimal:
    try:
        v = Decimal(text.strip())
    except (InvalidOperation, AttributeError):
        raise ValidationError(code, f"{what} '{text}' is not a number")
    if not v.is_finite():
        raise ValidationError(code, f"{what} '{text}' is not a finite number")
    return v


def parse_rr(text: str) -> str:                                   # VR-01
    rr = (text or "").strip().upper()
    if not _RR_RE.match(rr):
        raise ValidationError("VR-01", f"RR number '{text}' must be 4-20 letters, digits or hyphens (e.g. RR-BG-50108)")
    return rr


def parse_category(text: str) -> str:                             # VR-02
    cat = (text or "").strip().upper()
    if cat not in CATEGORIES:
        raise ValidationError("VR-02", f"category '{text}' must be DOMESTIC or COMMERCIAL")
    return cat


def parse_load(text: str) -> Decimal:                             # VR-03
    v = _dec(text or "", "VR-03", "sanctioned load")
    if v <= 0:
        raise ValidationError("VR-03", f"sanctioned load {v} kW must be greater than 0")
    if v != v.quantize(Decimal("0.01")):
        raise ValidationError("VR-03", f"sanctioned load {v} kW has more than 2 decimals")
    return v


def parse_meter(text: str, what: str, code: str) -> int:          # VR-04 / VR-07
    t = (text or "").strip()
    if not t.isdigit() or len(t) > len(str(METER_MAX)):
        raise ValidationError(code, f"{what} '{text}' must be a whole number of at most 5 digits")
    return int(t)                                                  # '00012' -> 12


def parse_date(text: str, what: str, code: str) -> date:         # VR-05 / VR-10
    try:
        return datetime.strptime((text or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError(code, f"{what} '{text}' is not a valid date (YYYY-MM-DD)")


def parse_pf(text: str, category: str):                           # VR-08 / VR-09
    t = (text or "").strip()
    if category != "COMMERCIAL":
        return None                      # BR-04: PF is irrelevant to DOMESTIC; 'NONE'/blank/any value ignored
    if t == "" or t.upper() == "NONE":
        raise ValidationError("VR-08", "average PF is mandatory for a COMMERCIAL reading (got blank/NONE)")
    v = _dec(t, "VR-09", "average PF")
    if not (Decimal("0") <= v <= Decimal("1")):        # 0.00 is legal: zero-consumption commercial month
        raise ValidationError("VR-09", f"average PF {v} must be in the range [0, 1]")
    return v


def parse_month(text: str) -> str:                                # VR-11
    t = (text or "").strip()
    if not _MONTH_RE.match(t):
        raise ValidationError("VR-11", f"month '{text}' must look like YYYY-MM")
    return t


def parse_amount(text: str) -> Decimal:                           # VR-12
    v = _dec(text or "", "VR-12", "payment amount")
    if v <= 0:
        raise ValidationError("VR-12", f"payment amount {v} must be greater than 0")
    if v != v.quantize(Decimal("0.01")):
        raise ValidationError("VR-12", f"payment amount {v} has more than 2 decimals")
    return v
