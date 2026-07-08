"""Deterministic financial analytics engine.

Turns raw customer data (transactions, budget, savings, goals) into a
:class:`FinancialSnapshot`. All numbers the coach relies on are computed here
so they are auditable and testable; the LLM only explains these figures, never
invents them.
"""
from __future__ import annotations

from collections import defaultdict

from coach.core.config import Settings
from coach.domain.entities import (
    CategorySpend,
    CustomerFinancialProfile,
    FinancialSnapshot,
)
from coach.domain.enums import SpendCategory, TransactionType

_ESSENTIAL = {
    SpendCategory.HOUSING,
    SpendCategory.FOOD,
    SpendCategory.UTILITIES,
    SpendCategory.TRANSPORT,
    SpendCategory.HEALTH,
    SpendCategory.EMI,
}


class FinancialAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _months_observed(profile: CustomerFinancialProfile) -> int:
        months = {(t.date.year, t.date.month) for t in profile.transactions}
        return max(1, len(months))

    def _monthly_income(self, profile: CustomerFinancialProfile, months: int) -> float:
        if profile.budget and profile.budget.monthly_income > 0:
            return float(profile.budget.monthly_income)
        credits = sum(
            t.amount
            for t in profile.transactions
            if t.type == TransactionType.CREDIT and t.category == SpendCategory.INCOME
        )
        return round(credits / months, 2)

    def _monthly_spend_by_category(
        self, profile: CustomerFinancialProfile, months: int
    ) -> dict[SpendCategory, float]:
        totals: dict[SpendCategory, float] = defaultdict(float)
        for t in profile.transactions:
            if t.type == TransactionType.DEBIT:
                totals[t.category] += t.amount
        return {cat: round(amt / months, 2) for cat, amt in totals.items()}

    # -- main ----------------------------------------------------------------
    def build_snapshot(self, profile: CustomerFinancialProfile) -> FinancialSnapshot:
        months = self._months_observed(profile)
        income = self._monthly_income(profile, months)
        by_cat = self._monthly_spend_by_category(profile, months)

        # Investments/SIP are savings, not consumption expenses.
        expense_cats = {c: a for c, a in by_cat.items() if c != SpendCategory.INVESTMENTS}
        monthly_expenses = round(sum(expense_cats.values()), 2)
        total_emi = round(by_cat.get(SpendCategory.EMI, 0.0), 2)

        surplus = round(income - monthly_expenses, 2)
        savings_rate = round((surplus / income * 100) if income > 0 else 0.0, 1)

        total_savings = round(sum(s.balance for s in profile.savings), 2)
        total_sip = round(
            sum(s.monthly_sip for s in profile.savings)
            + by_cat.get(SpendCategory.INVESTMENTS, 0.0),
            2,
        )
        ef_balance = round(
            sum(s.balance for s in profile.savings if s.is_emergency_fund), 2
        )
        essential_spend = sum(
            a for c, a in expense_cats.items() if c in _ESSENTIAL
        ) or monthly_expenses
        ef_months = round(ef_balance / essential_spend, 1) if essential_spend > 0 else 0.0
        foir = round((total_emi / income * 100) if income > 0 else 0.0, 1)

        # Category breakdown with budget comparison.
        breakdown: list[CategorySpend] = []
        overspending: list[CategorySpend] = []
        budget = profile.budget
        for cat, amount in sorted(expense_cats.items(), key=lambda kv: kv[1], reverse=True):
            share = round((amount / monthly_expenses * 100) if monthly_expenses else 0.0, 1)
            limit = budget.limit_for(cat) if budget else None
            over = bool(limit is not None and amount > limit * 1.05)
            cs = CategorySpend(
                category=cat,
                amount=amount,
                share_pct=share,
                budget_limit=limit,
                over_budget=over,
            )
            breakdown.append(cs)
            if over:
                overspending.append(cs)

        return FinancialSnapshot(
            monthly_income=income,
            monthly_expenses=monthly_expenses,
            monthly_surplus=surplus,
            savings_rate_pct=savings_rate,
            total_savings=total_savings,
            total_sip=total_sip,
            emergency_fund_balance=ef_balance,
            emergency_fund_months=ef_months,
            total_monthly_emi=total_emi,
            foir_pct=foir,
            top_categories=breakdown[:6],
            overspending_categories=overspending,
            months_observed=months,
        )

    def health_score(self, snapshot: FinancialSnapshot) -> tuple[float, str]:
        """0-100 composite financial-health score with a letter grade."""
        s = self._settings
        # Savings rate component (0-40).
        sr = max(0.0, min(1.0, snapshot.savings_rate_pct / s.healthy_savings_rate_pct))
        savings_pts = sr * 40
        # Emergency fund component (0-30).
        ef = max(0.0, min(1.0, snapshot.emergency_fund_months / s.emergency_fund_months))
        ef_pts = ef * 30
        # Debt/FOIR component (0-20): full marks at 0% FOIR, zero at/above cap.
        foir_ratio = max(0.0, min(1.0, snapshot.foir_pct / s.max_foir_pct))
        debt_pts = (1.0 - foir_ratio) * 20
        # Budget discipline component (0-10).
        discipline_pts = 10.0 if not snapshot.overspending_categories else max(
            0.0, 10.0 - 2.5 * len(snapshot.overspending_categories)
        )
        score = round(savings_pts + ef_pts + debt_pts + discipline_pts, 1)
        grade = (
            "A" if score >= 85 else
            "B" if score >= 70 else
            "C" if score >= 55 else
            "D" if score >= 40 else
            "E"
        )
        return score, grade
