"""In-memory customer financial-data repository with realistic seed data.

Implements :class:`ICustomerRepository`. In production this adapter would wrap
a core-banking / data-warehouse API; the seed data lets the service run and be
demoed end-to-end offline. The public contract (``get_profile``) is unchanged
regardless of backing store.
"""
from __future__ import annotations

import datetime as dt

from coach.core.exceptions import CustomerNotFoundError
from coach.domain.entities import (
    Budget,
    BudgetLine,
    CustomerFinancialProfile,
    Goal,
    SavingsAccount,
    Transaction,
)
from coach.domain.enums import SpendCategory, TransactionType
from coach.domain.interfaces.customer import ICustomerRepository


def _recent_transactions(reference: dt.date) -> list[Transaction]:
    """Generate ~3 months of representative monthly transactions."""
    txns: list[Transaction] = []
    monthly = [
        (SpendCategory.INCOME, TransactionType.CREDIT, 220000, "Salary credit", "Employer"),
        (SpendCategory.HOUSING, TransactionType.DEBIT, 45000, "Rent", "Landlord"),
        (SpendCategory.EMI, TransactionType.DEBIT, 18000, "Personal loan EMI", "Bank"),
        (SpendCategory.FOOD, TransactionType.DEBIT, 24000, "Groceries & dining", "Various"),
        (SpendCategory.TRANSPORT, TransactionType.DEBIT, 9000, "Fuel & cabs", "Various"),
        (SpendCategory.UTILITIES, TransactionType.DEBIT, 6500, "Electricity & internet", "Utility"),
        (SpendCategory.SHOPPING, TransactionType.DEBIT, 22000, "Online shopping", "Marketplace"),
        (SpendCategory.ENTERTAINMENT, TransactionType.DEBIT, 11000, "Streaming & outings", "Various"),
        (SpendCategory.INVESTMENTS, TransactionType.DEBIT, 25000, "SIP auto-debit", "AMC"),
    ]
    seq = 0
    for month_offset in range(3):
        month_date = reference.replace(day=1) - dt.timedelta(days=30 * month_offset)
        for category, ttype, amount, desc, merchant in monthly:
            seq += 1
            # Add mild variability to discretionary spend for realism.
            jitter = 1.0
            if category in {SpendCategory.SHOPPING, SpendCategory.ENTERTAINMENT}:
                jitter = 1.0 + (0.15 if month_offset == 0 else -0.05 * month_offset)
            txns.append(
                Transaction(
                    id=f"txn-{seq:04d}",
                    date=month_date + dt.timedelta(days=2),
                    amount=round(amount * jitter, 2),
                    type=ttype,
                    category=category,
                    description=desc,
                    merchant=merchant,
                )
            )
    return txns


def _seed() -> dict[str, CustomerFinancialProfile]:
    today = dt.date(2026, 7, 1)
    profile = CustomerFinancialProfile(
        customer_id="cust-001",
        display_name="Ada Lovelace",
        currency="INR",
        transactions=_recent_transactions(today),
        budget=Budget(
            monthly_income=220000,
            lines=[
                BudgetLine(SpendCategory.HOUSING, 45000),
                BudgetLine(SpendCategory.FOOD, 22000),
                BudgetLine(SpendCategory.TRANSPORT, 10000),
                BudgetLine(SpendCategory.UTILITIES, 7000),
                BudgetLine(SpendCategory.SHOPPING, 15000),
                BudgetLine(SpendCategory.ENTERTAINMENT, 8000),
            ],
        ),
        savings=[
            SavingsAccount(name="Emergency Fund", balance=350000, is_emergency_fund=True),
            SavingsAccount(name="Mutual Fund SIP", balance=640000, monthly_sip=25000),
            SavingsAccount(name="Savings Account", balance=180000),
        ],
        goals=[
            Goal(
                name="Car down payment",
                target_amount=400000,
                saved_amount=150000,
                target_date=dt.date(2027, 6, 1),
                priority="high",
            ),
            Goal(
                name="Home down payment",
                target_amount=3000000,
                saved_amount=800000,
                target_date=dt.date(2030, 1, 1),
                priority="high",
            ),
            Goal(
                name="Retirement",
                target_amount=50000000,
                saved_amount=640000,
                priority="medium",
            ),
        ],
    )
    return {profile.customer_id: profile}


class InMemoryCustomerRepository(ICustomerRepository):
    def __init__(self, seed: dict[str, CustomerFinancialProfile] | None = None) -> None:
        self._store: dict[str, CustomerFinancialProfile] = seed if seed is not None else _seed()

    async def get_profile(self, customer_id: str) -> CustomerFinancialProfile:
        profile = self._store.get(customer_id)
        if profile is None:
            raise CustomerNotFoundError(
                f"No financial profile found for customer '{customer_id}'."
            )
        return profile

    def upsert(self, profile: CustomerFinancialProfile) -> None:
        """Test / seeding helper."""
        self._store[profile.customer_id] = profile
