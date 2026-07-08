"""OpenBB Market Data — a Clean-Architecture FastAPI market-data integration service.

Retrieves stocks, mutual funds, ETFs, gold, indices, market news, financial
ratios and historical prices from OpenBB behind stable domain ports, with
production concerns (caching, retries, rate-limit handling) implemented once in
the service layer rather than scattered across endpoints.
"""
