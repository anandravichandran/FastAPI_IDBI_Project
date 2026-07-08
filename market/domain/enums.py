"""Domain enumerations."""
from __future__ import annotations

from enum import Enum


class AssetClass(str, Enum):
    STOCK = "stock"
    MUTUAL_FUND = "mutual_fund"
    ETF = "etf"
    GOLD = "gold"
    INDEX = "index"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()


class ProviderBackend(str, Enum):
    OPENBB = "openbb"
    SYNTHETIC = "synthetic"


class Interval(str, Enum):
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1m"

    @classmethod
    def from_str(cls, value: str | None) -> "Interval":
        """Parse a user-supplied interval leniently, defaulting to daily."""
        if value is None:
            return cls.DAY
        normalised = value.strip().lower()
        aliases = {
            "1d": cls.DAY, "d": cls.DAY, "day": cls.DAY, "daily": cls.DAY,
            "1w": cls.WEEK, "w": cls.WEEK, "wk": cls.WEEK, "week": cls.WEEK,
            "weekly": cls.WEEK,
            "1m": cls.MONTH, "mo": cls.MONTH, "month": cls.MONTH,
            "monthly": cls.MONTH,
        }
        if normalised in aliases:
            return aliases[normalised]
        from market.core.exceptions import DomainValidationError

        raise DomainValidationError(
            f"Unsupported interval: {value!r}. Use one of 1d, 1w, 1m."
        )
