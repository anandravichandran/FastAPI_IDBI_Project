"""Port: customer financial-data provider."""
from __future__ import annotations

from abc import ABC, abstractmethod

from coach.domain.entities import CustomerFinancialProfile


class ICustomerRepository(ABC):
    """Loads a customer's transactions, budget, savings and goals.

    Concrete adapters can wrap a core-banking API, a data warehouse, or (as
    shipped) an in-memory seed store. The service layer depends only on this
    abstraction.
    """

    @abstractmethod
    async def get_profile(self, customer_id: str) -> CustomerFinancialProfile:
        """Return the full financial profile for ``customer_id``.

        Raises:
            CustomerNotFoundError: if no profile exists.
        """
        raise NotImplementedError
