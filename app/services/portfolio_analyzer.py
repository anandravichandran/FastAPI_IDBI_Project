"""Deterministic financial-planning engine.

All numeric outputs (risk score, target allocation, SIP, emergency fund,
diversification score) are computed here with transparent, testable rules.
The LLM layer only produces the narrative explanation, so the service stays
deterministic and auditable even when the model is unavailable. This is a
pure, side-effect-free component (Single Responsibility).
"""
from __future__ import annotations

from collections import defaultdict

from app.core.config import Settings
from app.domain.enums import (
    AssetClass,
    EmergencyFundStatus,
    RiskBand,
    RiskTolerance,
)
from app.schemas.request import AdviceRequest
from app.schemas.response import (
    AllocationItem,
    AssetAllocation,
    CurrentAllocationItem,
    DiversificationAdvice,
    EmergencyFundRecommendation,
    PortfolioAnalysis,
    RiskScore,
    SIPRecommendation,
)

_TOLERANCE_BASE = {
    RiskTolerance.CONSERVATIVE: 30.0,
    RiskTolerance.MODERATE: 55.0,
    RiskTolerance.AGGRESSIVE: 78.0,
}

# Strategic target equity weight by tolerance; the remainder is split across
# fixed income, cash, and diversifiers.
_TARGET_TEMPLATES: dict[RiskTolerance, dict[AssetClass, float]] = {
    RiskTolerance.CONSERVATIVE: {
        AssetClass.EQUITY: 30.0,
        AssetClass.FIXED_INCOME: 45.0,
        AssetClass.CASH: 15.0,
        AssetClass.COMMODITIES: 5.0,
        AssetClass.REAL_ESTATE: 5.0,
    },
    RiskTolerance.MODERATE: {
        AssetClass.EQUITY: 55.0,
        AssetClass.FIXED_INCOME: 25.0,
        AssetClass.CASH: 5.0,
        AssetClass.COMMODITIES: 7.5,
        AssetClass.REAL_ESTATE: 7.5,
    },
    RiskTolerance.AGGRESSIVE: {
        AssetClass.EQUITY: 75.0,
        AssetClass.FIXED_INCOME: 12.5,
        AssetClass.CASH: 2.5,
        AssetClass.COMMODITIES: 5.0,
        AssetClass.REAL_ESTATE: 5.0,
    },
}

_EXPECTED_RETURN = {
    AssetClass.EQUITY: 12.0,
    AssetClass.FIXED_INCOME: 7.0,
    AssetClass.CASH: 4.0,
    AssetClass.REAL_ESTATE: 9.0,
    AssetClass.COMMODITIES: 6.0,
    AssetClass.CRYPTO: 18.0,
    AssetClass.OTHER: 6.0,
}


class PortfolioAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # -- Risk ----------------------------------------------------------------
    def compute_risk_score(self, request: AdviceRequest) -> RiskScore:
        base = _TOLERANCE_BASE[request.risk_profile.tolerance]
        horizon = request.risk_profile.investment_horizon_years
        horizon_adj = min(15.0, (horizon - 10) * 0.8)
        age_adj = -min(15.0, max(0.0, (request.user_profile.age - 40) * 0.4))
        income_adj = -6.0 if not request.risk_profile.has_stable_income else 0.0
        dependents_adj = -min(8.0, request.user_profile.dependents * 2.0)
        score = max(0.0, min(100.0, base + horizon_adj + age_adj + income_adj + dependents_adj))
        return RiskScore(
            score=round(score, 1),
            band=self._risk_band(score),
            rationale=(
                f"Derived from a {request.risk_profile.tolerance.value} tolerance, a "
                f"{horizon}-year horizon, age {request.user_profile.age}, "
                f"{request.user_profile.dependents} dependent(s), and "
                f"{'stable' if request.risk_profile.has_stable_income else 'variable'} income."
            ),
        )

    @staticmethod
    def _risk_band(score: float) -> RiskBand:
        if score < 20:
            return RiskBand.VERY_LOW
        if score < 40:
            return RiskBand.LOW
        if score < 60:
            return RiskBand.MODERATE
        if score < 80:
            return RiskBand.HIGH
        return RiskBand.VERY_HIGH

    # -- Portfolio snapshot --------------------------------------------------
    def analyze_portfolio(self, request: AdviceRequest) -> PortfolioAnalysis:
        total = request.portfolio_value
        by_class: dict[AssetClass, float] = defaultdict(float)
        for holding in request.current_portfolio:
            by_class[holding.asset_class] += holding.current_value

        current_allocation = [
            CurrentAllocationItem(
                asset_class=asset_class,
                current_pct=round((value / total) * 100, 2) if total else 0.0,
                current_value=round(value, 2),
            )
            for asset_class, value in sorted(
                by_class.items(), key=lambda kv: kv[1], reverse=True
            )
        ]

        largest_position_pct = 0.0
        if total:
            largest_position_pct = round(
                max(h.current_value for h in request.current_portfolio) / total * 100, 2
            )

        observations: list[str] = []
        if total == 0:
            observations.append("No existing holdings; recommendations start from a clean slate.")
        if largest_position_pct > 10:
            observations.append(
                f"Largest single position is {largest_position_pct:.1f}% of the portfolio, "
                "above the 10% concentration guideline."
            )
        equity_pct = next(
            (a.current_pct for a in current_allocation if a.asset_class == AssetClass.EQUITY),
            0.0,
        )
        target_equity = _TARGET_TEMPLATES[request.risk_profile.tolerance][AssetClass.EQUITY]
        if total and abs(equity_pct - target_equity) >= 10:
            direction = "above" if equity_pct > target_equity else "below"
            observations.append(
                f"Equity weight ({equity_pct:.1f}%) is well {direction} the "
                f"{target_equity:.0f}% strategic target."
            )

        return PortfolioAnalysis(
            total_value=round(total, 2),
            holdings_count=len(request.current_portfolio),
            largest_position_pct=largest_position_pct,
            current_allocation=current_allocation,
            observations=observations,
        )

    # -- Target allocation ---------------------------------------------------
    def target_allocation(self, request: AdviceRequest) -> AssetAllocation:
        template = _TARGET_TEMPLATES[request.risk_profile.tolerance]
        # Nudge toward safety for short horizons.
        template = self._adjust_for_horizon(template, request.risk_profile.investment_horizon_years)
        items = [
            AllocationItem(
                asset_class=asset_class,
                target_pct=round(pct, 1),
                rationale=self._allocation_rationale(asset_class),
            )
            for asset_class, pct in template.items()
            if pct > 0
        ]
        summary = (
            f"A {request.risk_profile.tolerance.value} allocation anchored on "
            f"{template[AssetClass.EQUITY]:.0f}% equity, diversified across fixed income, "
            "cash and real assets, sized to the stated horizon."
        )
        return AssetAllocation(target=items, summary=summary)

    @staticmethod
    def _adjust_for_horizon(
        template: dict[AssetClass, float], horizon_years: int
    ) -> dict[AssetClass, float]:
        if horizon_years >= 5:
            return dict(template)
        adjusted = dict(template)
        shift = 15.0 if horizon_years <= 2 else 8.0
        shift = min(shift, adjusted[AssetClass.EQUITY])
        adjusted[AssetClass.EQUITY] -= shift
        adjusted[AssetClass.FIXED_INCOME] += shift * 0.5
        adjusted[AssetClass.CASH] += shift * 0.5
        return adjusted

    @staticmethod
    def _allocation_rationale(asset_class: AssetClass) -> str:
        return {
            AssetClass.EQUITY: "Long-term growth engine.",
            AssetClass.FIXED_INCOME: "Income and volatility ballast.",
            AssetClass.CASH: "Liquidity and dry powder.",
            AssetClass.COMMODITIES: "Inflation hedge and diversifier.",
            AssetClass.REAL_ESTATE: "Real-asset diversification and yield.",
            AssetClass.CRYPTO: "High-risk satellite exposure.",
            AssetClass.OTHER: "Miscellaneous diversifier.",
        }.get(asset_class, "Diversifier.")

    # -- SIP -----------------------------------------------------------------
    def sip_recommendation(
        self, request: AdviceRequest, allocation: AssetAllocation
    ) -> SIPRecommendation:
        surplus = max(0.0, request.monthly_surplus)
        emergency_gap = self._emergency_shortfall(request)
        # Route a portion of surplus to close an emergency-fund gap first.
        investable = surplus * (0.6 if emergency_gap > 0 else 0.85)
        investable = round(max(0.0, investable), 2)

        allocations = [
            AllocationItem(
                asset_class=item.asset_class,
                target_pct=item.target_pct,
                rationale=f"{round(investable * item.target_pct / 100, 2)} per month",
            )
            for item in allocation.target
        ]
        expected_return = round(
            sum(
                _EXPECTED_RETURN.get(item.asset_class, 6.0) * item.target_pct / 100
                for item in allocation.target
            ),
            2,
        )
        notes = (
            f"Invest about {investable:,.0f} per month via SIP, split by the target "
            "allocation. "
            + (
                "A reduced rate is used while the emergency fund is being topped up."
                if emergency_gap > 0
                else "Surplus is largely deployed since the emergency fund is in place."
            )
        )
        return SIPRecommendation(
            recommended_monthly_amount=investable,
            allocations=allocations,
            expected_annual_return_pct=expected_return,
            notes=notes,
        )

    # -- Emergency fund ------------------------------------------------------
    def _emergency_target(self, request: AdviceRequest) -> float:
        months = self._settings.emergency_fund_months
        if request.user_profile.dependents > 0 or not request.risk_profile.has_stable_income:
            months = max(months, 9.0)
        return round(request.monthly_expenses * months, 2)

    def _emergency_shortfall(self, request: AdviceRequest) -> float:
        return max(0.0, self._emergency_target(request) - request.current_savings)

    def emergency_fund(self, request: AdviceRequest) -> EmergencyFundRecommendation:
        target = self._emergency_target(request)
        months = target / request.monthly_expenses if request.monthly_expenses else 0.0
        coverage = (
            request.current_savings / request.monthly_expenses
            if request.monthly_expenses
            else 0.0
        )
        shortfall = max(0.0, target - request.current_savings)
        if coverage >= months:
            status = EmergencyFundStatus.FULLY_FUNDED
        elif coverage >= months * 0.5:
            status = EmergencyFundStatus.ON_TRACK
        else:
            status = EmergencyFundStatus.UNDERFUNDED
        notes = (
            f"Target {months:.0f} months of expenses ({target:,.0f}). "
            f"Current savings cover about {coverage:.1f} months."
        )
        return EmergencyFundRecommendation(
            recommended_amount=target,
            months_of_expenses=round(months, 1),
            current_coverage_months=round(coverage, 1),
            shortfall=round(shortfall, 2),
            status=status,
            notes=notes,
        )

    # -- Diversification -----------------------------------------------------
    def diversification(
        self, request: AdviceRequest, analysis: PortfolioAnalysis
    ) -> DiversificationAdvice:
        issues: list[str] = []
        recommendations: list[str] = []

        distinct_classes = len(analysis.current_allocation)
        total = analysis.total_value

        if total == 0:
            return DiversificationAdvice(
                diversification_score=0.0,
                issues=["No holdings to diversify yet."],
                recommendations=[
                    "Begin building positions per the target allocation via SIP."
                ],
            )

        # Herfindahl-Hirschman Index on asset-class weights -> diversification.
        weights = [a.current_pct / 100 for a in analysis.current_allocation]
        hhi = sum(w * w for w in weights)
        div_score = round(max(0.0, min(100.0, (1 - hhi) * 100)), 1)

        if analysis.largest_position_pct > 10:
            issues.append(
                f"Single-position concentration at {analysis.largest_position_pct:.1f}%."
            )
            recommendations.append("Trim outsized positions toward a <10% per-holding cap.")
        if distinct_classes < 3:
            issues.append("Exposure spans fewer than three asset classes.")
            recommendations.append(
                "Add fixed income and a real-asset/commodity sleeve for balance."
            )
        equity_item = next(
            (a for a in analysis.current_allocation if a.asset_class == AssetClass.EQUITY),
            None,
        )
        target_equity = _TARGET_TEMPLATES[request.risk_profile.tolerance][AssetClass.EQUITY]
        if equity_item and equity_item.current_pct - target_equity > 10:
            recommendations.append(
                "Rebalance equity down toward target on a threshold (5%) basis."
            )
        if not recommendations:
            recommendations.append("Maintain allocation and rebalance annually.")

        return DiversificationAdvice(
            diversification_score=div_score,
            issues=issues,
            recommendations=recommendations,
        )
