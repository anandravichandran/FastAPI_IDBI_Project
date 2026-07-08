"""Unified ASGI entrypoint for the Financial Suite.

The suite is a **modular monolith**: six independently-developed FastAPI
applications — the *Investment Advisor*, the *Financial Coach*, the *Budget
Planner*, the *Savings Optimizer*, the *RAG Service* and the *Market Data
Service* — are mounted as isolated sub-applications under a single parent app.
Each keeps its own Clean-Architecture stack (domain / services / repositories /
API), its own OpenAPI docs, middleware and exception handling, so they can
evolve and deploy together without leaking implementation details into one
another.

Run with:
    uvicorn server:app --reload

Route map
---------
    /                              suite metadata
    /health                        aggregate liveness probe
    /docs                          this page (links to every sub-app)

    /advisor/docs                  Investment Advisor OpenAPI docs
    /advisor/api/v1/health         Advisor health
    /advisor/api/v1/advisor        POST  → investment advice

    /coach/docs                    Financial Coach OpenAPI docs
    /coach/api/v1/health           Coach health
    /coach/api/v1/coach/chat       POST  → conversational coaching
    /coach/api/v1/coach/history    GET   → conversation history
    /coach/api/v1/coach/summary    GET   → financial-health summary

    /budget/docs                   Budget Planner OpenAPI docs
    /budget/api/v1/health          Budget health
    /budget/api/v1/budget/plan     POST  → monthly budget plan

    /savings/docs                  Savings Optimizer OpenAPI docs
    /savings/api/v1/health         Savings health
    /savings/api/v1/savings/optimize  POST  → savings & investment plan

    /rag/docs                      RAG Service OpenAPI docs
    /rag/api/v1/health             RAG health
    /rag/api/v1/documents          POST  → upload & index a PDF
    /rag/api/v1/documents          GET   → list indexed documents
    /rag/api/v1/documents/{id}     DELETE → remove a document
    /rag/api/v1/rag/query          POST  → retrieve relevant chunks
    /rag/api/v1/rag/context        POST  → grounded context for DeepSeek

    /market/docs                   Market Data OpenAPI docs
    /market/api/v1/health          Market Data health
    /market/api/v1/stocks/{s}/quote      GET → stock quote
    /market/api/v1/stocks/{s}/historical GET → historical prices
    /market/api/v1/stocks/{s}/ratios     GET → financial ratios
    /market/api/v1/mutual-funds/{s}      GET → mutual fund quote
    /market/api/v1/etf/{s}               GET → ETF quote
    /market/api/v1/gold                  GET → spot gold
    /market/api/v1/indices/{s}           GET → index quote
    /market/api/v1/news                  GET/POST → market news
    /market/api/v1/cache/stats           GET → cache statistics
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from advisor.api.deps import shutdown_dependencies as shutdown_advisor
from advisor.main import create_app as create_advisor_app
from budget.api.deps import shutdown_dependencies as shutdown_budget
from budget.main import create_app as create_budget_app
from coach.api.deps import shutdown_dependencies as shutdown_coach
from coach.main import create_app as create_coach_app
from market.api.deps import shutdown_dependencies as shutdown_market
from market.main import create_app as create_market_app
from rag.api.deps import shutdown_dependencies as shutdown_rag
from rag.main import create_app as create_rag_app
from savings.api.deps import shutdown_dependencies as shutdown_savings
from savings.main import create_app as create_savings_app

__version__ = "1.4.0"

# Build each sub-application once at import time. Each factory configures its
# own logging, middleware, exception handlers and routes.
advisor_app = create_advisor_app()
coach_app = create_coach_app()
budget_app = create_budget_app()
savings_app = create_savings_app()
rag_app = create_rag_app()
market_app = create_market_app()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Starlette does not propagate lifespan to mounted sub-apps, so the parent
    # is responsible for releasing their pooled resources (HTTP clients, etc.).
    yield
    await shutdown_advisor()
    await shutdown_coach()
    await shutdown_budget()
    await shutdown_savings()
    await shutdown_rag()
    await shutdown_market()


app = FastAPI(
    title="Financial Suite",
    version=__version__,
    description=(
        "Enterprise financial-intelligence suite combining five FastAPI "
        "microservices behind one gateway:\n\n"
        "- **Investment Advisor** (`/advisor`) — portfolio analysis, risk "
        "scoring, asset allocation, SIP and emergency-fund recommendations, "
        "powered by OpenBB market data, RAG and DeepSeek V3.\n"
        "- **Financial Coach** (`/coach`) — conversational, avatar-ready "
        "coaching over the customer's transactions, budget, savings and "
        "goals, powered by RAG and DeepSeek V3.\n"
        "- **Budget Planner** (`/budget`) — deterministic monthly budgeting "
        "from income, expenses, bills and goals: recommended budget, expense "
        "breakdown, savings rate, alerts, overspending detection and a budget "
        "score.\n"
        "- **Savings Optimizer** (`/savings`) — deterministic savings & "
        "investment planning from salary, expenses, loans, savings and goals: "
        "emergency fund, monthly saving, SIP / fixed-deposit / liquid-fund "
        "split, investment allocation and a savings score.\n"
        "- **RAG Service** (`/rag`) — upload PDFs, chunk, embed with Sentence "
        "Transformers, store vectors in ChromaDB, retrieve relevant chunks and "
        "return grounded context ready for DeepSeek.\n"
        "- **Market Data Service** (`/market`) — OpenBB-backed retrieval of "
        "stocks, mutual funds, ETFs, gold, indices, market news, financial "
        "ratios and historical prices, with per-domain TTL caching, retries "
        "with backoff and client-side rate limiting.\n\n"
        "Each sub-app exposes its own docs at `/advisor/docs`, `/coach/docs`, "
        "`/budget/docs`, `/savings/docs`, `/rag/docs` and `/market/docs`."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={"name": "FinTech Platform Team"},
    license_info={"name": "MIT"},
)


@app.get("/", tags=["meta"], summary="Suite metadata")
async def root() -> dict[str, object]:
    return {
        "service": "Financial Suite",
        "version": __version__,
        "applications": {
            "advisor": {
                "base": "/advisor",
                "docs": "/advisor/docs",
                "advice": "/advisor/api/v1/advisor",
            },
            "coach": {
                "base": "/coach",
                "docs": "/coach/docs",
                "chat": "/coach/api/v1/coach/chat",
                "history": "/coach/api/v1/coach/history",
                "summary": "/coach/api/v1/coach/summary",
            },
            "budget": {
                "base": "/budget",
                "docs": "/budget/docs",
                "plan": "/budget/api/v1/budget/plan",
            },
            "savings": {
                "base": "/savings",
                "docs": "/savings/docs",
                "optimize": "/savings/api/v1/savings/optimize",
            },
            "rag": {
                "base": "/rag",
                "docs": "/rag/docs",
                "upload": "/rag/api/v1/documents",
                "query": "/rag/api/v1/rag/query",
                "context": "/rag/api/v1/rag/context",
            },
            "market": {
                "base": "/market",
                "docs": "/market/docs",
                "stocks": "/market/api/v1/stocks/{symbol}/quote",
                "news": "/market/api/v1/news",
                "cache_stats": "/market/api/v1/cache/stats",
            },
        },
    }


@app.get("/health", tags=["meta"], summary="Aggregate liveness probe")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "advisor": "mounted",
        "coach": "mounted",
        "budget": "mounted",
        "savings": "mounted",
        "rag": "mounted",
        "market": "mounted",
    }


@app.get("/advisor", include_in_schema=False)
async def _advisor_redirect() -> RedirectResponse:
    return RedirectResponse(url="/advisor/docs")


@app.get("/coach", include_in_schema=False)
async def _coach_redirect() -> RedirectResponse:
    return RedirectResponse(url="/coach/docs")


@app.get("/budget", include_in_schema=False)
async def _budget_redirect() -> RedirectResponse:
    return RedirectResponse(url="/budget/docs")


@app.get("/savings", include_in_schema=False)
async def _savings_redirect() -> RedirectResponse:
    return RedirectResponse(url="/savings/docs")


@app.get("/rag", include_in_schema=False)
async def _rag_redirect() -> RedirectResponse:
    return RedirectResponse(url="/rag/docs")


@app.get("/market", include_in_schema=False)
async def _market_redirect() -> RedirectResponse:
    return RedirectResponse(url="/market/docs")


# Mount the isolated sub-applications.
app.mount("/advisor", advisor_app)
app.mount("/coach", coach_app)
app.mount("/budget", budget_app)
app.mount("/savings", savings_app)
app.mount("/rag", rag_app)
app.mount("/market", market_app)
