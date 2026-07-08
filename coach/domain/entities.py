"""Framework-agnostic domain entities and value objects.

These dataclasses are the internal currency of the domain and service layers.
They are intentionally decoupled from Pydantic / FastAPI so business logic
never depends on transport or serialization concerns (Clean Architecture /
Dependency Inversion).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from coach.domain.enums import SpendCategory, TransactionType


@dataclass(frozen=True, slots=True)
class Transaction:
    id: str
    date: dt.date
    amount: float  # always positive; direction given by ``type``
    type: TransactionType
    category: SpendCategory
    description: str = ""
    merchant: str | None = None


@dataclass(frozen=True, slots=True)
class BudgetLine:
    category: SpendCategory
    monthly_limit: float


@dataclass(frozen=True, slots=True)
class Budget:
    monthly_income: float
    lines: list[BudgetLine] = field(default_factory=list)

    def limit_for(self, category: SpendCategory) -> float | None:
        for line in self.lines:
            if line.category == category:
                return line.monthly_limit
        return None


@dataclass(frozen=True, slots=True)
class SavingsAccount:
    name: str
    balance: float
    is_emergency_fund: bool = False
    monthly_sip: float = 0.0  # recurring auto-invest / SIP contribution


@dataclass(frozen=True, slots=True)
class Goal:
    name: str
    target_amount: float
    saved_amount: float = 0.0
    target_date: dt.date | None = None
    priority: str = "medium"

    @property
    def progress_pct(self) -> float:
        if self.target_amount <= 0:
            return 0.0
        return round(min(100.0, self.saved_amount / self.target_amount * 100), 1)


@dataclass(frozen=True, slots=True)
class CustomerFinancialProfile:
    """Everything the coach knows about a customer."""

    customer_id: str
    display_name: str
    currency: str
    transactions: list[Transaction] = field(default_factory=list)
    budget: Budget | None = None
    savings: list[SavingsAccount] = field(default_factory=list)
    goals: list[Goal] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CategorySpend:
    category: SpendCategory
    amount: float
    share_pct: float
    budget_limit: float | None = None
    over_budget: bool = False


@dataclass(frozen=True, slots=True)
class FinancialSnapshot:
    """Deterministically computed monthly financial picture."""

    monthly_income: float
    monthly_expenses: float
    monthly_surplus: float
    savings_rate_pct: float
    total_savings: float
    total_sip: float
    emergency_fund_balance: float
    emergency_fund_months: float
    total_monthly_emi: float
    foir_pct: float
    top_categories: list[CategorySpend] = field(default_factory=list)
    overspending_categories: list[CategorySpend] = field(default_factory=list)
    months_observed: int = 1


@dataclass(frozen=True, slots=True)
class KnowledgeSnippet:
    """A retrieved chunk of financial knowledge (RAG result)."""

    id: str
    title: str
    content: str
    score: float
    source: str = "coaching-kb"


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class LLMResult:
    """Raw completion returned by the language model."""

    content: str
    model: str
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    session_id: str
    customer_id: str
    role: str
    content: str
    created_at: dt.datetime
    intent: str | None = None
