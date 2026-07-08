"""The deterministic budget-planning engine.

This is the use-case core of the module. It is a pure, framework-agnostic
class: it takes normalized domain inputs and produces a fully-computed
:class:`BudgetPlan`. Every number is auditable and unit-tested — there is no
randomness and no external I/O, which makes budgeting behaviour predictable and
easy to reason about (important for a banking product).

Methodology
-----------
* All cash flows are normalized to a **monthly** basis.
* The **recommended budget** uses a configurable 50/30/20 (needs/wants/savings)
  framework scaled to the customer's income.
* **Overspending** is detected per category against its bucket-proportional
  recommendation, with a configurable tolerance.
* The **budget score** (0–100) blends savings rate, bucket discipline, bill
  burden and goal funding into a single, explainable grade.
"""
from __future__ import annotations

from collections import defaultdict

from budget.core.config import Settings
from budget.core.exceptions import DomainValidationError
from budget.domain.entities import (
    Alert,
    BucketSummary,
    BudgetPlan,
    BudgetRequestData,
    CategoryLine,
    GoalPlan,
    RecommendedBudget,
)
from budget.domain.enums import (
    AlertLevel,
    AlertType,
    BudgetBucket,
    ExpenseCategory,
    bucket_for,
    to_monthly,
)

_GRADE_BANDS = ((85, "A"), (70, "B"), (55, "C"), (40, "D"))


class BudgetPlanner:
    """Compute a recommended budget, diagnostics and a score from inputs."""

    def __init__(self, settings: Settings) -> None:
        self._s = settings

    # -- public API ----------------------------------------------------------
    def build_plan(self, data: BudgetRequestData) -> BudgetPlan:
        income = self._monthly_income(data)
        if income <= 0:
            raise DomainValidationError(
                "Total monthly income must be greater than zero.",
                details={"monthly_income": income},
            )

        # Aggregate spend per category from both expenses and bills.
        per_category, total_bills = self._aggregate(data)
        total_spend = round(sum(per_category.values()), 2)
        total_expenses = round(total_spend - total_bills, 2)

        # Savings = whatever income remains after all outflow, PLUS anything the
        # customer already routes into savings/investment categories.
        explicit_savings = sum(
            amt for cat, amt in per_category.items()
            if bucket_for(cat) is BudgetBucket.SAVINGS
        )
        non_savings_outflow = round(total_spend - explicit_savings, 2)
        residual = round(income - non_savings_outflow, 2)
        savings_amount = round(max(residual, 0.0) + explicit_savings, 2)
        # Net cashflow can go negative; that is an important signal we keep.
        net_cashflow = round(income - non_savings_outflow, 2)
        savings_pct = round(savings_amount / income * 100, 2)

        recommended = self._recommended_budget(income, data.currency)
        buckets = self._bucket_summaries(income, per_category, recommended)
        breakdown = self._breakdown(per_category, total_spend, recommended, buckets)
        overspending = tuple(line for line in breakdown if line.over_budget)
        goals = self._goal_plans(data, available=max(net_cashflow, 0.0))
        bill_burden_pct = round(total_bills / income * 100, 2)

        score, grade = self._score(
            savings_pct=savings_pct,
            buckets=buckets,
            bill_burden_pct=bill_burden_pct,
            goals=goals,
            overspending_count=len(overspending),
            net_cashflow=net_cashflow,
        )
        alerts = self._alerts(
            income=income,
            net_cashflow=net_cashflow,
            savings_pct=savings_pct,
            bill_burden_pct=bill_burden_pct,
            buckets=buckets,
            overspending=overspending,
            goals=goals,
            data=data,
        )
        highlights, recommendations = self._narrative(
            savings_pct, buckets, bill_burden_pct, overspending, goals, net_cashflow
        )

        return BudgetPlan(
            currency=data.currency,
            monthly_income=income,
            total_expenses=total_expenses,
            total_bills=round(total_bills, 2),
            total_outflow=non_savings_outflow,
            net_cashflow=net_cashflow,
            savings_amount=savings_amount,
            savings_pct=savings_pct,
            recommended_budget=recommended,
            buckets=buckets,
            breakdown=breakdown,
            goals=goals,
            overspending=overspending,
            alerts=alerts,
            budget_score=score,
            grade=grade,
            highlights=highlights,
            recommendations=recommendations,
        )

    # -- helpers -------------------------------------------------------------
    def _monthly_income(self, data: BudgetRequestData) -> float:
        return round(
            sum(to_monthly(i.amount, i.frequency) for i in data.incomes), 2
        )

    def _aggregate(
        self, data: BudgetRequestData
    ) -> tuple[dict[ExpenseCategory, float], float]:
        per_category: dict[ExpenseCategory, float] = defaultdict(float)
        for e in data.expenses:
            per_category[e.category] += to_monthly(e.amount, e.frequency)
        total_bills = 0.0
        for b in data.bills:
            monthly = to_monthly(b.amount, b.frequency)
            per_category[b.category] += monthly
            total_bills += monthly
        # round each category once
        return ({k: round(v, 2) for k, v in per_category.items()}, round(total_bills, 2))

    def _recommended_budget(self, income: float, currency: str) -> RecommendedBudget:
        return RecommendedBudget(
            needs=round(income * self._s.needs_target_pct / 100, 2),
            wants=round(income * self._s.wants_target_pct / 100, 2),
            savings=round(income * self._s.savings_target_pct / 100, 2),
            currency=currency,
        )

    def _bucket_summaries(
        self,
        income: float,
        per_category: dict[ExpenseCategory, float],
        recommended: RecommendedBudget,
    ) -> tuple[BucketSummary, ...]:
        actuals: dict[BudgetBucket, float] = defaultdict(float)
        for cat, amt in per_category.items():
            actuals[bucket_for(cat)] += amt

        targets = {
            BudgetBucket.NEEDS: (self._s.needs_target_pct, recommended.needs),
            BudgetBucket.WANTS: (self._s.wants_target_pct, recommended.wants),
            BudgetBucket.SAVINGS: (self._s.savings_target_pct, recommended.savings),
        }
        summaries: list[BucketSummary] = []
        for bucket in (BudgetBucket.NEEDS, BudgetBucket.WANTS, BudgetBucket.SAVINGS):
            actual = round(actuals.get(bucket, 0.0), 2)
            target_pct, rec = targets[bucket]
            actual_pct = round(actual / income * 100, 2) if income else 0.0
            over = actual_pct > target_pct + self._s.overspend_tolerance_pct
            # For savings, being ABOVE target is good, so never flag it.
            if bucket is BudgetBucket.SAVINGS:
                over = False
            summaries.append(
                BucketSummary(
                    bucket=bucket,
                    actual=actual,
                    actual_pct=actual_pct,
                    target_pct=target_pct,
                    recommended=rec,
                    variance=round(actual - rec, 2),
                    over_target=over,
                )
            )
        return tuple(summaries)

    def _breakdown(
        self,
        per_category: dict[ExpenseCategory, float],
        total_spend: float,
        recommended: RecommendedBudget,
        buckets: tuple[BucketSummary, ...],
    ) -> tuple[CategoryLine, ...]:
        # Recommended per category = its share of the bucket's actual spend,
        # applied to the bucket's recommended envelope. This distributes the
        # 50/30/20 envelope proportionally to where the customer already spends.
        bucket_actual = {b.bucket: b.actual for b in buckets}
        bucket_rec = {b.bucket: b.recommended for b in buckets}
        tol = self._s.overspend_tolerance_pct / 100

        lines: list[CategoryLine] = []
        for cat, actual in per_category.items():
            bucket = bucket_for(cat)
            b_actual = bucket_actual.get(bucket, 0.0)
            b_rec = bucket_rec.get(bucket, 0.0)
            rec = round((actual / b_actual) * b_rec, 2) if b_actual > 0 else 0.0
            share = round(actual / total_spend * 100, 2) if total_spend else 0.0
            variance = round(actual - rec, 2)
            # Savings categories are never "over budget".
            over = (
                bucket is not BudgetBucket.SAVINGS
                and rec > 0
                and actual > rec * (1 + tol)
            )
            lines.append(
                CategoryLine(
                    category=cat,
                    bucket=bucket,
                    actual=actual,
                    share_pct=share,
                    recommended=rec,
                    variance=variance,
                    over_budget=over,
                )
            )
        lines.sort(key=lambda line: line.actual, reverse=True)
        return tuple(lines)

    def _goal_plans(
        self, data: BudgetRequestData, *, available: float
    ) -> tuple[GoalPlan, ...]:
        # Fund goals greedily by priority, then by required amount.
        order = {"high": 0, "medium": 1, "low": 2}
        ranked = sorted(
            data.goals,
            key=lambda g: (order.get(g.priority.value, 1), -g.required_monthly()),
        )
        remaining = available
        plans: list[GoalPlan] = []
        for g in ranked:
            required = g.required_monthly()
            funded = round(min(required, remaining), 2) if required > 0 else 0.0
            remaining = round(remaining - funded, 2)
            plans.append(
                GoalPlan(
                    name=g.name,
                    target_amount=g.target_amount,
                    saved_amount=g.saved_amount,
                    progress_pct=g.progress_pct,
                    required_monthly=required,
                    funded_monthly=funded,
                    fully_funded=required <= 0 or funded + 1e-6 >= required,
                    priority=g.priority,
                )
            )
        return tuple(plans)

    def _score(
        self,
        *,
        savings_pct: float,
        buckets: tuple[BucketSummary, ...],
        bill_burden_pct: float,
        goals: tuple[GoalPlan, ...],
        overspending_count: int,
        net_cashflow: float,
    ) -> tuple[float, str]:
        by_bucket = {b.bucket: b for b in buckets}

        # 1) Savings rate vs target (40 pts).
        target = self._s.savings_target_pct or 20.0
        savings_score = max(0.0, min(savings_pct / target, 1.0)) * 40

        # 2) Needs discipline vs target (25 pts) — penalize overshoot only.
        needs = by_bucket.get(BudgetBucket.NEEDS)
        needs_over = max(0.0, (needs.actual_pct if needs else 0.0) - needs.target_pct) if needs else 0.0
        needs_score = max(0.0, 1 - needs_over / 25) * 25

        # 3) Wants discipline vs target (15 pts).
        wants = by_bucket.get(BudgetBucket.WANTS)
        wants_over = max(0.0, (wants.actual_pct if wants else 0.0) - wants.target_pct) if wants else 0.0
        wants_score = max(0.0, 1 - wants_over / 20) * 15

        # 4) Bill burden (10 pts) — lower is better, warn threshold = full penalty.
        warn = self._s.bill_burden_warn_pct or 35.0
        bill_score = max(0.0, 1 - bill_burden_pct / (warn * 2)) * 10

        # 5) Goal funding coverage (10 pts).
        req = sum(g.required_monthly for g in goals)
        funded = sum(g.funded_monthly for g in goals)
        goal_score = 10.0 if req <= 0 else max(0.0, min(funded / req, 1.0)) * 10

        total = savings_score + needs_score + wants_score + bill_score + goal_score
        # Hard penalties for structurally unhealthy budgets.
        if net_cashflow < 0:
            total -= 15
        total -= min(overspending_count, 5) * 2
        score = round(max(0.0, min(total, 100.0)), 1)

        grade = "E"
        for threshold, letter in _GRADE_BANDS:
            if score >= threshold:
                grade = letter
                break
        return score, grade

    def _alerts(
        self,
        *,
        income: float,
        net_cashflow: float,
        savings_pct: float,
        bill_burden_pct: float,
        buckets: tuple[BucketSummary, ...],
        overspending: tuple[CategoryLine, ...],
        goals: tuple[GoalPlan, ...],
        data: BudgetRequestData,
    ) -> tuple[Alert, ...]:
        alerts: list[Alert] = []

        if net_cashflow < 0:
            alerts.append(Alert(
                AlertLevel.CRITICAL, AlertType.NEGATIVE_CASHFLOW,
                f"You are spending {abs(net_cashflow):,.0f} {data.currency} more than "
                f"you earn each month.",
            ))

        if savings_pct < self._s.min_savings_pct:
            alerts.append(Alert(
                AlertLevel.CRITICAL if savings_pct <= 0 else AlertLevel.WARNING,
                AlertType.LOW_SAVINGS,
                f"Savings rate is {savings_pct}% — below the {self._s.min_savings_pct}% "
                f"minimum.",
            ))

        if bill_burden_pct > self._s.bill_burden_warn_pct:
            alerts.append(Alert(
                AlertLevel.WARNING, AlertType.HIGH_BILL_BURDEN,
                f"Fixed bills consume {bill_burden_pct}% of income (warn above "
                f"{self._s.bill_burden_warn_pct}%).",
            ))

        for b in buckets:
            if b.over_target:
                alerts.append(Alert(
                    AlertLevel.WARNING, AlertType.BUCKET_OVER_TARGET,
                    f"{b.bucket.value.capitalize()} spending is {b.actual_pct}% of "
                    f"income vs a {b.target_pct}% target.",
                ))

        for line in overspending:
            alerts.append(Alert(
                AlertLevel.WARNING, AlertType.OVERSPENDING,
                f"Overspending on {line.category.value} by "
                f"{line.variance:,.0f} {data.currency}/mo vs recommendation.",
                category=line.category,
            ))

        for g in goals:
            if not g.fully_funded:
                shortfall = round(g.required_monthly - g.funded_monthly, 2)
                alerts.append(Alert(
                    AlertLevel.WARNING, AlertType.GOAL_UNDERFUNDED,
                    f"Goal '{g.name}' is underfunded by {shortfall:,.0f} "
                    f"{data.currency}/mo at current cash flow.",
                ))

        # Upcoming-bill reminders (informational).
        due_soon = sorted(
            (b for b in data.bills if b.due_day and not b.autopay),
            key=lambda b: b.due_day or 32,
        )[:3]
        for b in due_soon:
            alerts.append(Alert(
                AlertLevel.INFO, AlertType.BILL_DUE_SOON,
                f"'{b.name}' ({b.amount:,.0f} {data.currency}) is due on day "
                f"{b.due_day} and is not on autopay.",
                category=b.category,
            ))

        if not alerts:
            alerts.append(Alert(
                AlertLevel.INFO, AlertType.POSITIVE,
                f"Your budget looks healthy — {savings_pct}% saved with no "
                f"overspending detected.",
            ))
        return tuple(alerts)

    def _narrative(
        self,
        savings_pct: float,
        buckets: tuple[BucketSummary, ...],
        bill_burden_pct: float,
        overspending: tuple[CategoryLine, ...],
        goals: tuple[GoalPlan, ...],
        net_cashflow: float,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        highlights: list[str] = []
        recs: list[str] = []

        if savings_pct >= self._s.savings_target_pct:
            highlights.append(f"Strong {savings_pct}% savings rate, at or above target.")
        elif net_cashflow >= 0:
            recs.append(
                f"Lift savings from {savings_pct}% toward {self._s.savings_target_pct}% "
                f"by trimming discretionary spend."
            )
        else:
            recs.append("Bring spending below income to stop drawing down reserves.")

        wants = next((b for b in buckets if b.bucket is BudgetBucket.WANTS), None)
        if wants and wants.over_target:
            recs.append(
                f"Reduce wants by {abs(wants.variance):,.0f} to reach the "
                f"{wants.target_pct}% guideline."
            )
        if overspending:
            names = ", ".join(line.category.value for line in overspending[:3])
            recs.append(f"Set category caps for: {names}.")
        if bill_burden_pct > self._s.bill_burden_warn_pct:
            recs.append("Renegotiate or consolidate fixed bills to lower recurring load.")
        underfunded = [g for g in goals if not g.fully_funded]
        if underfunded:
            recs.append(
                f"Free up cash flow to fully fund {len(underfunded)} goal(s)."
            )
        if not recs:
            recs.append("Maintain course and automate transfers on payday.")
        return tuple(highlights), tuple(recs)
