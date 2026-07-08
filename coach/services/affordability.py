"""Deterministic affordability & recommendation engine.

Each method answers one coaching question with an auditable verdict, numeric
basis and short human reasons. The coach service passes these results to the
LLM for narration — the LLM must not change the numbers or the verdict.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from coach.core.config import Settings
from coach.domain.entities import CustomerFinancialProfile, FinancialSnapshot
from coach.domain.enums import Verdict


@dataclass(frozen=True, slots=True)
class Assessment:
    """Structured result of a single coaching question."""

    verdict: Verdict
    headline: str
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    actions: list[str] = field(default_factory=list)


def _emi(principal: float, annual_rate_pct: float, years: int) -> float:
    """Standard reducing-balance EMI."""
    if principal <= 0 or years <= 0:
        return 0.0
    r = annual_rate_pct / 100 / 12
    n = years * 12
    if r == 0:
        return round(principal / n, 2)
    factor = (1 + r) ** n
    return round(principal * r * factor / (factor - 1), 2)


class AffordabilityEngine:
    def __init__(self, settings: Settings) -> None:
        self._s = settings

    # -- Can I buy a car? ----------------------------------------------------
    def assess_car(
        self,
        snapshot: FinancialSnapshot,
        profile: CustomerFinancialProfile,
        price: float | None,
    ) -> Assessment:
        s = self._s
        income = snapshot.monthly_income
        # Estimate a car price from goals if the user didn't give one.
        if price is None:
            price = next(
                (g.target_amount * 3 for g in profile.goals if "car" in g.name.lower()),
                600000.0,
            )
        down_payment = round(price * 0.20, 2)
        loan_amount = round(price - down_payment, 2)
        emi = _emi(loan_amount, s.car_loan_rate_pct, s.default_car_loan_years)
        # Running costs ~ 3% of price per year.
        running = round(price * 0.03 / 12, 2)
        total_transport_cost = emi + running
        transport_pct = round(total_transport_cost / income * 100, 1) if income else 0.0
        new_foir = round(
            (snapshot.total_monthly_emi + emi) / income * 100, 1
        ) if income else 0.0
        ef_ok = snapshot.emergency_fund_months >= s.emergency_fund_months * 0.75
        cash_ok = snapshot.total_savings >= down_payment * 1.5

        metrics = {
            "assumed_price": round(price, 2),
            "down_payment": down_payment,
            "loan_amount": loan_amount,
            "estimated_emi": emi,
            "transport_cost_pct": transport_pct,
            "projected_foir_pct": new_foir,
            "monthly_surplus": snapshot.monthly_surplus,
        }
        reasons: list[str] = []
        actions: list[str] = []

        affordable_emi = emi <= snapshot.monthly_surplus * 0.6
        foir_ok = new_foir <= s.max_foir_pct
        transport_ok = transport_pct <= 10.0

        if affordable_emi and foir_ok and transport_ok and ef_ok:
            verdict = Verdict.YES
            headline = "Yes — a car looks affordable within healthy limits."
            reasons.append(
                f"Estimated EMI ₹{emi:,.0f} fits inside your ₹{snapshot.monthly_surplus:,.0f} monthly surplus."
            )
            reasons.append(f"Projected debt load (FOIR) stays at {new_foir}%, under the {s.max_foir_pct:.0f}% guideline.")
        elif (affordable_emi or foir_ok) and (ef_ok or cash_ok):
            verdict = Verdict.CAUTION
            headline = "Maybe — possible, but tighten the plan first."
            if not transport_ok:
                reasons.append(f"Total car cost would be {transport_pct}% of income, above the 10% comfort line.")
            if not affordable_emi:
                reasons.append(f"EMI ₹{emi:,.0f} uses a large share of your ₹{snapshot.monthly_surplus:,.0f} surplus.")
            actions.append("Increase the down payment or pick a cheaper model to cut the EMI.")
        else:
            verdict = Verdict.NO
            headline = "Not yet — buying now would strain your finances."
            if not foir_ok:
                reasons.append(f"Projected FOIR {new_foir}% exceeds the {s.max_foir_pct:.0f}% safe limit.")
            if not affordable_emi:
                reasons.append(f"EMI ₹{emi:,.0f} is too large for your ₹{snapshot.monthly_surplus:,.0f} surplus.")
            if not ef_ok:
                reasons.append("Emergency fund is below the recommended buffer.")
            actions.append("Build the down payment and emergency fund before financing a car.")
        if not ef_ok:
            actions.append(f"Top up the emergency fund toward {s.emergency_fund_months:.0f} months of expenses.")
        return Assessment(verdict, headline, reasons, metrics, actions)

    # -- Can I afford a home loan? ------------------------------------------
    def assess_home_loan(
        self,
        snapshot: FinancialSnapshot,
        profile: CustomerFinancialProfile,
        property_price: float | None,
    ) -> Assessment:
        s = self._s
        income = snapshot.monthly_income
        if property_price is None:
            property_price = next(
                (g.target_amount * 10 for g in profile.goals if "home" in g.name.lower() or "house" in g.name.lower()),
                8000000.0,
            )
        down_payment = round(property_price * 0.20, 2)
        loan_amount = round(property_price - down_payment, 2)
        emi = _emi(loan_amount, s.home_loan_rate_pct, s.default_home_loan_years)
        housing_emi_pct = round(emi / income * 100, 1) if income else 0.0
        new_foir = round((snapshot.total_monthly_emi + emi) / income * 100, 1) if income else 0.0
        # Eligibility rule of thumb: bank funds EMI up to (max_foir - existing).
        headroom = max(0.0, s.max_foir_pct - snapshot.foir_pct) / 100 * income
        max_supportable_loan = _reverse_emi(headroom, s.home_loan_rate_pct, s.default_home_loan_years)
        cash_for_dp = snapshot.total_savings - snapshot.emergency_fund_balance

        metrics = {
            "assumed_property_price": round(property_price, 2),
            "down_payment": down_payment,
            "loan_amount": loan_amount,
            "estimated_emi": emi,
            "housing_emi_pct": housing_emi_pct,
            "projected_foir_pct": new_foir,
            "max_supportable_loan": round(max_supportable_loan, 2),
            "cash_available_for_down_payment": round(cash_for_dp, 2),
        }
        reasons: list[str] = []
        actions: list[str] = []

        foir_ok = new_foir <= s.max_foir_pct
        emi_ratio_ok = housing_emi_pct <= 35.0
        dp_ok = cash_for_dp >= down_payment

        if foir_ok and emi_ratio_ok and dp_ok:
            verdict = Verdict.YES
            headline = "Yes — a home loan is within reach."
            reasons.append(f"Housing EMI ₹{emi:,.0f} is {housing_emi_pct}% of income, within the 35% norm.")
            reasons.append(f"Projected FOIR {new_foir}% stays under the {s.max_foir_pct:.0f}% limit.")
        elif foir_ok or emi_ratio_ok:
            verdict = Verdict.CAUTION
            headline = "Maybe — borderline; adjust the ticket size."
            if not emi_ratio_ok:
                reasons.append(f"Housing EMI would be {housing_emi_pct}% of income, above the 35% comfort zone.")
            if not dp_ok:
                reasons.append(f"Down payment ₹{down_payment:,.0f} exceeds free cash ₹{max(cash_for_dp,0):,.0f} (excl. emergency fund).")
            actions.append(f"Target a loan near ₹{max_supportable_loan:,.0f} to stay within safe limits.")
        else:
            verdict = Verdict.NO
            headline = "Not yet — this loan size would overextend you."
            reasons.append(f"Projected FOIR {new_foir}% exceeds the {s.max_foir_pct:.0f}% safe limit.")
            actions.append(f"Consider a smaller loan (~₹{max_supportable_loan:,.0f}) or grow income/down payment first.")
        if not dp_ok:
            actions.append("Accumulate at least a 20% down payment without touching the emergency fund.")
        return Assessment(verdict, headline, reasons, metrics, actions)

    # -- Should I increase SIP? ---------------------------------------------
    def assess_increase_sip(self, snapshot: FinancialSnapshot, extra: float | None) -> Assessment:
        s = self._s
        surplus = snapshot.monthly_surplus
        # Keep a 30% cushion of surplus unallocated.
        investable = max(0.0, round(surplus * 0.7 - snapshot.total_sip * 0.0, 2))
        suggested = extra if extra is not None else round(max(0.0, surplus * 0.5), -2)
        ef_ok = snapshot.emergency_fund_months >= s.emergency_fund_months

        metrics = {
            "current_sip": snapshot.total_sip,
            "monthly_surplus": surplus,
            "headroom_for_investing": investable,
            "suggested_increase": suggested,
            "emergency_fund_months": snapshot.emergency_fund_months,
        }
        reasons: list[str] = []
        actions: list[str] = []

        if not ef_ok:
            verdict = Verdict.CAUTION
            headline = "Build the safety net before adding to SIP."
            reasons.append(
                f"Emergency fund covers {snapshot.emergency_fund_months} months vs the {s.emergency_fund_months:.0f}-month target."
            )
            actions.append("Direct extra cash to the emergency fund first, then step up the SIP.")
        elif surplus <= 0:
            verdict = Verdict.NO
            headline = "No spare cash to increase SIP right now."
            reasons.append("Monthly expenses currently consume all of your income.")
            actions.append("Free up surplus by trimming discretionary spend, then revisit.")
        elif investable >= (suggested or 1):
            verdict = Verdict.YES
            headline = "Yes — you can comfortably step up your SIP."
            reasons.append(f"You have ₹{investable:,.0f}/month of investable headroom after a safety cushion.")
            actions.append(f"Increase SIP by about ₹{suggested:,.0f}/month via a step-up mandate.")
        else:
            verdict = Verdict.CAUTION
            headline = "A modest SIP increase is feasible."
            reasons.append(f"Investable headroom is about ₹{investable:,.0f}/month.")
            actions.append(f"Raise SIP by up to ₹{investable:,.0f}/month to stay comfortable.")
        return Assessment(verdict, headline, reasons, metrics, actions)

    # -- Am I overspending? --------------------------------------------------
    def assess_overspending(self, snapshot: FinancialSnapshot) -> Assessment:
        s = self._s
        over = snapshot.overspending_categories
        metrics = {
            "savings_rate_pct": snapshot.savings_rate_pct,
            "monthly_expenses": snapshot.monthly_expenses,
            "monthly_surplus": snapshot.monthly_surplus,
            "over_budget_categories": float(len(over)),
        }
        reasons: list[str] = []
        actions: list[str] = []
        if not over and snapshot.savings_rate_pct >= s.healthy_savings_rate_pct:
            verdict = Verdict.YES  # "yes you're on track" -> positive
            headline = "You're spending within your means."
            reasons.append(f"Savings rate is {snapshot.savings_rate_pct}%, at or above the {s.healthy_savings_rate_pct:.0f}% healthy mark.")
        elif over:
            verdict = Verdict.CAUTION
            names = ", ".join(c.category.value for c in over[:3])
            headline = f"A few categories are over budget: {names}."
            for c in over[:3]:
                reasons.append(
                    f"{c.category.value.title()}: ₹{c.amount:,.0f}/mo vs ₹{(c.budget_limit or 0):,.0f} budget."
                )
            actions.append("Set category caps and use a 24-hour rule for discretionary buys.")
        else:
            verdict = Verdict.CAUTION
            headline = "Spending is on budget, but your savings rate is low."
            reasons.append(f"Savings rate is {snapshot.savings_rate_pct}%, below the {s.healthy_savings_rate_pct:.0f}% target.")
            actions.append("Automate a fixed transfer on payday to lift the savings rate.")
        return Assessment(verdict, headline, reasons, metrics, actions)

    # -- How can I improve savings? -----------------------------------------
    def assess_improve_savings(self, snapshot: FinancialSnapshot) -> Assessment:
        s = self._s
        target_rate = s.healthy_savings_rate_pct
        gap_amount = round(
            max(0.0, (target_rate - snapshot.savings_rate_pct) / 100 * snapshot.monthly_income), 2
        )
        metrics = {
            "savings_rate_pct": snapshot.savings_rate_pct,
            "target_savings_rate_pct": target_rate,
            "monthly_gap_to_target": gap_amount,
            "monthly_surplus": snapshot.monthly_surplus,
        }
        actions = [
            "Automate a payday transfer to savings (pay yourself first).",
            "Cap the top discretionary categories and review subscriptions.",
            "Route raises and windfalls to investments before lifestyle creep.",
        ]
        reasons = []
        if snapshot.savings_rate_pct >= target_rate:
            verdict = Verdict.YES
            headline = "Your savings rate is already healthy — here's how to push further."
            reasons.append(f"Current rate {snapshot.savings_rate_pct}% meets the {target_rate:.0f}% target.")
        else:
            verdict = Verdict.INFO
            headline = f"Aim to save about ₹{gap_amount:,.0f} more per month."
            reasons.append(
                f"That closes the gap from {snapshot.savings_rate_pct}% to the {target_rate:.0f}% target rate."
            )
            if snapshot.overspending_categories:
                top = snapshot.overspending_categories[0]
                reasons.append(f"Start with {top.category.value} — currently over budget.")
        return Assessment(verdict, headline, reasons, metrics, actions)


def _reverse_emi(affordable_emi: float, annual_rate_pct: float, years: int) -> float:
    """Given an affordable monthly EMI, return the supportable loan principal."""
    if affordable_emi <= 0:
        return 0.0
    r = annual_rate_pct / 100 / 12
    n = years * 12
    if r == 0:
        return round(affordable_emi * n, 2)
    factor = (1 + r) ** n
    return round(affordable_emi * (factor - 1) / (r * factor), 2)
