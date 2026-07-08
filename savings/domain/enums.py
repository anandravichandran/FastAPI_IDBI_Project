"""Domain enumerations for the Savings Optimizer."""
from __future__ import annotations

from enum import Enum


class RiskProfile(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class GoalPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Instrument(str, Enum):
    """Destination buckets for monthly savings."""

    SIP = "sip"                # systematic investment plan (equity mutual funds)
    FIXED_DEPOSIT = "fixed_deposit"
    LIQUID_FUND = "liquid_fund"


class EmergencyFundStatus(str, Enum):
    UNDERFUNDED = "underfunded"
    ON_TRACK = "on_track"
    FULLY_FUNDED = "fully_funded"


class SavingsGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
