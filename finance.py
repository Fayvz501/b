"""Финансовые формулы: аннуитетный и дифференцированный платежи."""
from dataclasses import dataclass
from typing import List


@dataclass
class PaymentRow:
    month: int
    payment: float
    principal: float
    interest: float
    balance: float


@dataclass
class LoanResult:
    schedule: List[PaymentRow]
    total_paid: float
    total_interest: float
    first_payment: float
    last_payment: float


def annuity(amount: float, annual_rate: float, months: int) -> LoanResult:
    """Аннуитет: P = S * i*(1+i)^n / ((1+i)^n - 1)."""
    i = annual_rate / 100 / 12
    if i == 0:
        pmt = amount / months
    else:
        pmt = amount * (i * (1 + i) ** months) / ((1 + i) ** months - 1)

    schedule, balance = [], amount
    for m in range(1, months + 1):
        interest = balance * i
        principal = pmt - interest
        balance = max(0.0, balance - principal)
        schedule.append(PaymentRow(m, pmt, principal, interest, balance))

    total = pmt * months
    return LoanResult(schedule, total, total - amount, pmt, pmt)


def differentiated(amount: float, annual_rate: float, months: int) -> LoanResult:
    """Дифференцированный: principal = S/n, interest = balance*i."""
    i = annual_rate / 100 / 12
    principal_part = amount / months

    schedule, balance, total = [], amount, 0.0
    for m in range(1, months + 1):
        interest = balance * i
        pmt = principal_part + interest
        balance = max(0.0, balance - principal_part)
        schedule.append(PaymentRow(m, pmt, principal_part, interest, balance))
        total += pmt

    return LoanResult(
        schedule, total, total - amount,
        schedule[0].payment, schedule[-1].payment
    )
