"""The deterministic savings-optimization engine.

This is the use-case core of the module: a pure, framework-agnostic class that
takes normalized domain inputs and produces a fully-computed
:class:`SavingsPlan`. Every figure is auditable and unit-tested — no randomness,
no external I/O — which is essential for a banking product.

Methodology
-----------
1. **Disposable income** = salary − living expenses − total EMIs.
2. **Emergency fund** target = ``emergency_fund_months`` × (expenses + EMIs).
   The plan first steers savings into a *liquid* buffer until this is funded.
3. **Monthly saving** = the investable disposable income (never negative).
4. **Allocation** across **SIP / Fixed Deposit / Liquid fund** follows a
   waterfall: while the emergency fund is short, bias to liquid; once funded,
   apply a risk-based growth preset (conservative / moderate / aggressive),
   nudged by the customer's goal horizons.
5. **Savings score** (0–100) blends savings rate, emergency-fund coverage,
   debt burden (FOIR) and goal-funding readiness into an explainable grade.
"""
from __future__ import annotations

from savings.core.config import Settings
from savings.core.exceptions import DomainValidationError
from savings.domain.entities import (
    Alert,
    AllocationLine,
    EmergencyFund,
    GoalProjection,
    SavingsPlan,
    SavingsRequestData,
)
from savings.domain.enums import (
    AlertLevel,
    EmergencyFundStatus,
    Instrument,
    RiskProfile,
    SavingsGrade,
)

_GRADE_BANDS = ((85, SavingsGrade.A), (70, SavingsGrade.B), (55, SavingsGrade.C), (40, SavingsGrade.D))


class SavingsOptimizer:
    """Compute an emergency fund, monthly saving, instrument split and score."""

    def __init__(self, settings: Settings) -> None:
        self._s = settings

    # -- public API ----------------------------------------------------------
    def build_plan(self, data: SavingsRequestData) -> SavingsPlan:
        if data.monthly_salary <= 0:
            raise DomainValidationError(
                "Monthly salary must be greater than zero.",
                details={"monthly_salary": data.monthly_salary},
            )
        if data.monthly_expenses < 0 or data.current_savings < 0:
            raise DomainValidationError("Expenses and savings cannot be negative.")

        salary = round(data.monthly_salary, 2)
        expenses = round(data.monthly_expenses, 2)
        total_emi = round(sum(loan.emi for loan in data.loans), 2)
        disposable = round(salary - expenses - total_emi, 2)
        monthly_saving = round(max(disposable, 0.0), 2)
        savings_rate = round(monthly_saving / salary * 100, 2)
        foir = round(total_emi / salary * 100, 2)

        ef = self._emergency_fund(expenses, total_emi, data.current_savings, monthly_saving)
        allocation = self._allocation(monthly_saving, ef, data)
        by_instrument = {line.instrument: line.monthly_amount for line in allocation}
        goals = self._goal_projections(data, monthly_saving, ef)

        score, grade = self._score(
            savings_rate=savings_rate,
            ef=ef,
            foir=foir,
            goals=goals,
            disposable=disposable,
        )
        alerts = self._alerts(
            data=data, disposable=disposable, savings_rate=savings_rate,
            foir=foir, ef=ef, goals=goals,
        )
        highlights, recs = self._narrative(savings_rate, ef, foir, goals, disposable)

        return SavingsPlan(
            currency=data.currency,
            monthly_salary=salary,
            monthly_expenses=expenses,
            total_emi=total_emi,
            disposable_income=disposable,
            recommended_monthly_saving=monthly_saving,
            savings_rate_pct=savings_rate,
            foir_pct=foir,
            emergency_fund=ef,
            recommended_sip=by_instrument.get(Instrument.SIP, 0.0),
            recommended_fixed_deposit=by_instrument.get(Instrument.FIXED_DEPOSIT, 0.0),
            recommended_liquid_fund=by_instrument.get(Instrument.LIQUID_FUND, 0.0),
            investment_allocation=allocation,
            risk_profile=data.risk_profile,
            goals=goals,
            alerts=alerts,
            savings_score=score,
            grade=grade.value,
            highlights=highlights,
            recommendations=recs,
        )

    # -- helpers -------------------------------------------------------------
    def _emergency_fund(
        self, expenses: float, total_emi: float, current: float, monthly_saving: float
    ) -> EmergencyFund:
        monthly_burn = expenses + total_emi
        target = round(self._s.emergency_fund_months * monthly_burn, 2)
        coverage = round(current / target, 4) if target > 0 else 1.0
        months_covered = round(current / monthly_burn, 2) if monthly_burn > 0 else 0.0
        shortfall = round(max(target - current, 0.0), 2)

        if coverage >= 1.0:
            status = EmergencyFundStatus.FULLY_FUNDED
            top_up = 0.0
        else:
            status = (
                EmergencyFundStatus.ON_TRACK
                if coverage >= 0.5
                else EmergencyFundStatus.UNDERFUNDED
            )
            # Aim to close the gap within 12 months, capped by what's available.
            desired = round(shortfall / 12, 2)
            top_up = round(min(desired, monthly_saving), 2) if monthly_saving > 0 else desired
        return EmergencyFund(
            target=target,
            current=round(current, 2),
            coverage_ratio=round(min(coverage, 1.0), 4),
            months_covered=months_covered,
            shortfall=shortfall,
            monthly_top_up=top_up,
            status=status,
        )

    def _preset(self, ef: EmergencyFund, risk: RiskProfile) -> tuple[float, float, float]:
        """Return (sip_pct, fd_pct, liquid_pct) for the current situation."""
        s = self._s
        if ef.status is not EmergencyFundStatus.FULLY_FUNDED:
            return (s.ef_building_sip_pct, s.ef_building_fd_pct, s.ef_building_liquid_pct)
        if risk is RiskProfile.CONSERVATIVE:
            return (s.conservative_sip_pct, s.conservative_fd_pct, s.conservative_liquid_pct)
        if risk is RiskProfile.AGGRESSIVE:
            return (s.aggressive_sip_pct, s.aggressive_fd_pct, s.aggressive_liquid_pct)
        return (s.moderate_sip_pct, s.moderate_fd_pct, s.moderate_liquid_pct)

    def _allocation(
        self, monthly_saving: float, ef: EmergencyFund, data: SavingsRequestData
    ) -> tuple[AllocationLine, ...]:
        sip_pct, fd_pct, liquid_pct = self._preset(ef, data.risk_profile)

        # Nudge by goal horizon: predominantly short-horizon goals shift weight
        # from SIP (equity) toward FD/liquid; long horizons do the reverse.
        horizons = [g.horizon_months for g in data.goals if g.horizon_months]
        if horizons and ef.status is EmergencyFundStatus.FULLY_FUNDED:
            avg = sum(horizons) / len(horizons)
            if avg <= self._s.short_horizon_months:
                shift = min(sip_pct, 15.0)
                sip_pct -= shift
                fd_pct += shift
            elif avg >= self._s.long_horizon_months:
                shift = min(fd_pct + liquid_pct, 10.0)
                sip_pct += shift
                fd_pct = max(fd_pct - shift, 0.0)

        # Normalize to 100 to guard against rounding/nudge drift.
        total = sip_pct + fd_pct + liquid_pct
        if total <= 0:
            sip_pct, fd_pct, liquid_pct, total = 0.0, 0.0, 100.0, 100.0
        sip_pct, fd_pct, liquid_pct = (
            round(sip_pct / total * 100, 2),
            round(fd_pct / total * 100, 2),
            round(liquid_pct / total * 100, 2),
        )

        building = ef.status is not EmergencyFundStatus.FULLY_FUNDED
        lines = [
            AllocationLine(
                Instrument.SIP, sip_pct, round(monthly_saving * sip_pct / 100, 2),
                "Long-term wealth via equity mutual-fund SIPs"
                if not building else "Modest equity exposure while building the buffer",
            ),
            AllocationLine(
                Instrument.FIXED_DEPOSIT, fd_pct, round(monthly_saving * fd_pct / 100, 2),
                "Capital-protected returns for medium-term goals",
            ),
            AllocationLine(
                Instrument.LIQUID_FUND, liquid_pct, round(monthly_saving * liquid_pct / 100, 2),
                "Building the emergency fund with instant access"
                if building else "Ready cash for near-term needs",
            ),
        ]
        return tuple(lines)

    def _goal_projections(
        self, data: SavingsRequestData, monthly_saving: float, ef: EmergencyFund
    ) -> tuple[GoalProjection, ...]:
        # Goals are funded from savings left after the emergency-fund top-up.
        order = {"high": 0, "medium": 1, "low": 2}
        ranked = sorted(
            data.goals,
            key=lambda g: (order.get(g.priority.value, 1), -g.required_monthly()),
        )
        available = round(max(monthly_saving - ef.monthly_top_up, 0.0), 2)
        projections: list[GoalProjection] = []
        for g in ranked:
            required = g.required_monthly()
            funded = round(min(required, available), 2) if required > 0 else 0.0
            available = round(available - funded, 2)
            projections.append(
                GoalProjection(
                    name=g.name,
                    target_amount=g.target_amount,
                    saved_amount=g.saved_amount,
                    progress_pct=g.progress_pct,
                    required_monthly=required,
                    funded_monthly=funded,
                    on_track=required <= 0 or funded + 1e-6 >= required,
                    priority=g.priority,
                )
            )
        return tuple(projections)

    def _score(
        self,
        *,
        savings_rate: float,
        ef: EmergencyFund,
        foir: float,
        goals: tuple[GoalProjection, ...],
        disposable: float,
    ) -> tuple[float, SavingsGrade]:
        # 1) Savings rate vs target (35 pts).
        target = self._s.healthy_savings_rate_pct or 20.0
        savings_score = max(0.0, min(savings_rate / target, 1.0)) * 35

        # 2) Emergency-fund coverage (30 pts).
        ef_score = max(0.0, min(ef.coverage_ratio, 1.0)) * 30

        # 3) Debt burden / FOIR (20 pts) — lower is better; full penalty at ceiling.
        ceiling = self._s.max_foir_pct or 40.0
        debt_score = max(0.0, 1 - foir / ceiling) * 20

        # 4) Goal-funding readiness (15 pts).
        req = sum(g.required_monthly for g in goals)
        funded = sum(g.funded_monthly for g in goals)
        goal_score = 15.0 if req <= 0 else max(0.0, min(funded / req, 1.0)) * 15

        total = savings_score + ef_score + debt_score + goal_score
        if disposable <= 0:
            total -= 20  # cannot save at all this month
        score = round(max(0.0, min(total, 100.0)), 1)

        grade = SavingsGrade.E
        for threshold, letter in _GRADE_BANDS:
            if score >= threshold:
                grade = letter
                break
        return score, grade

    def _alerts(
        self,
        *,
        data: SavingsRequestData,
        disposable: float,
        savings_rate: float,
        foir: float,
        ef: EmergencyFund,
        goals: tuple[GoalProjection, ...],
    ) -> tuple[Alert, ...]:
        alerts: list[Alert] = []
        cur = data.currency

        if disposable <= 0:
            alerts.append(Alert(
                AlertLevel.CRITICAL, "no_surplus",
                f"Expenses and EMIs consume your entire salary — no monthly "
                f"surplus to save ({disposable:,.0f} {cur}).",
            ))
        elif savings_rate < self._s.healthy_savings_rate_pct:
            alerts.append(Alert(
                AlertLevel.WARNING, "low_savings_rate",
                f"Savings rate is {savings_rate}% — below the "
                f"{self._s.healthy_savings_rate_pct}% target.",
            ))

        if foir > self._s.max_foir_pct:
            alerts.append(Alert(
                AlertLevel.WARNING, "high_debt_burden",
                f"Loan EMIs are {foir}% of salary (FOIR ceiling "
                f"{self._s.max_foir_pct}%). Consider prepaying high-rate loans.",
            ))

        if ef.status is EmergencyFundStatus.UNDERFUNDED:
            alerts.append(Alert(
                AlertLevel.CRITICAL if ef.months_covered < 1 else AlertLevel.WARNING,
                "emergency_fund_low",
                f"Emergency fund covers only {ef.months_covered} months — target is "
                f"{self._s.emergency_fund_months:g}. Top up ~{ef.monthly_top_up:,.0f} "
                f"{cur}/mo.",
            ))
        elif ef.status is EmergencyFundStatus.ON_TRACK:
            alerts.append(Alert(
                AlertLevel.INFO, "emergency_fund_building",
                f"Emergency fund is {round(ef.coverage_ratio * 100)}% funded — keep "
                f"topping up ~{ef.monthly_top_up:,.0f} {cur}/mo.",
            ))

        for g in goals:
            if not g.on_track:
                gap = round(g.required_monthly - g.funded_monthly, 2)
                alerts.append(Alert(
                    AlertLevel.WARNING, "goal_underfunded",
                    f"Goal '{g.name}' is short by {gap:,.0f} {cur}/mo at current "
                    f"savings.",
                ))

        if not alerts:
            alerts.append(Alert(
                AlertLevel.INFO, "healthy",
                f"Strong position — {savings_rate}% saved and emergency fund fully "
                f"funded.",
            ))
        return tuple(alerts)

    def _narrative(
        self,
        savings_rate: float,
        ef: EmergencyFund,
        foir: float,
        goals: tuple[GoalProjection, ...],
        disposable: float,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        highlights: list[str] = []
        recs: list[str] = []

        if savings_rate >= self._s.healthy_savings_rate_pct:
            highlights.append(f"Healthy {savings_rate}% savings rate.")
        if ef.status is EmergencyFundStatus.FULLY_FUNDED:
            highlights.append(f"Emergency fund fully funded ({ef.months_covered} months).")

        if disposable <= 0:
            recs.append("Reduce expenses or restructure loans to create a monthly surplus.")
        elif savings_rate < self._s.healthy_savings_rate_pct:
            recs.append(
                f"Trim discretionary spending to lift savings toward "
                f"{self._s.healthy_savings_rate_pct}%."
            )
        if ef.status is not EmergencyFundStatus.FULLY_FUNDED:
            recs.append(
                f"Prioritise the emergency fund: route ~{ef.monthly_top_up:,.0f} "
                f"{ef.current and ''}to a liquid fund each month."
            )
        if foir > self._s.max_foir_pct:
            recs.append("Prepay or refinance high-interest loans to lower EMI burden.")
        underfunded = [g for g in goals if not g.on_track]
        if underfunded:
            recs.append(f"Stagger or extend {len(underfunded)} goal(s) to fit cash flow.")
        if ef.status is EmergencyFundStatus.FULLY_FUNDED and not underfunded:
            recs.append("Automate SIPs on salary day and review allocation annually.")
        if not recs:
            recs.append("Maintain course and automate transfers on payday.")
        return tuple(highlights), tuple(recs)
