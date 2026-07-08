"""Domain enumerations shared across layers."""
from __future__ import annotations

from enum import Enum


class CoachIntent(str, Enum):
    BUY_CAR = "buy_car"
    INCREASE_SIP = "increase_sip"
    HOME_LOAN = "home_loan"
    OVERSPENDING = "overspending"
    IMPROVE_SAVINGS = "improve_savings"
    GENERAL = "general"


class Verdict(str, Enum):
    """Traffic-light style assessment used to drive avatar behaviour."""

    YES = "yes"
    CAUTION = "caution"
    NO = "no"
    INFO = "info"


class AvatarEmotion(str, Enum):
    HAPPY = "happy"
    ENCOURAGING = "encouraging"
    NEUTRAL = "neutral"
    CONCERNED = "concerned"
    CELEBRATING = "celebrating"


class TransactionType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"


class SpendCategory(str, Enum):
    HOUSING = "housing"
    FOOD = "food"
    TRANSPORT = "transport"
    UTILITIES = "utilities"
    SHOPPING = "shopping"
    ENTERTAINMENT = "entertainment"
    HEALTH = "health"
    EDUCATION = "education"
    INVESTMENTS = "investments"
    EMI = "emi"
    INCOME = "income"
    OTHER = "other"


class MessageRole(str, Enum):
    USER = "user"
    COACH = "coach"
