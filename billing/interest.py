"""BR-07 late-payment interest - rule as fixed by the official 10 SECONDS pack.

For every payment made AFTER its bill's due date:
    interest = 1% x bill total x ceil(days late / 30)         (2 dp, half-up)
and it appears as the late-interest line on the consumer's FIRST bill whose
bill date is strictly AFTER the payment date. Paid on the due date = on time.
Interest is not taxed. Unpaid bills attract no interest (only late payments do).
"""
from decimal import Decimal
from datetime import date

from . import config as cfg
from .models import Bill, Payment
from .money import q2


def periods_overdue(due: date, paid: date) -> int:
    """30-day periods (or part) between the due date and the payment date."""
    days = (paid - due).days
    if days <= 0:
        return 0
    return -(-days // cfg.LATE_PERIOD_DAYS)          # ceiling division


def interest_for_payment(bill: Bill, payment: Payment) -> Decimal:
    return q2(bill.total * cfg.LATE_RATE_PER_PERIOD * periods_overdue(bill.due_date, payment.pay_date))
