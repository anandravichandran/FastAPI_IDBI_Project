"""Unified ASGI entrypoint for the Financial Suite.

The suite is a **modular monolith**: four independently-developed FastAPI
applications — the *Investment Advisor*, the *Financial Coach*, the *Budget
Planner* and the *Savings Optimizer* — are mounted as isolated sub-applications
under a single parent app.
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
from savings.api.deps import shutdown_dependencies as shutdown_savings
from savings.main import create_app as create_savings_app

__version__ = "1.2.0"

# Build each sub-application once at import time. Each factory configures its
# own logging, middleware, exception handlers and routes.
advisor_app = create_advisor_app()
coach_app = create_coach_app()
budget_app = create_budget_app()
savings_app = create_savings_app()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Starlette does not propagate lifespan to mounted sub-apps, so the parent
    # is responsible for releasing their pooled resources (HTTP clients, etc.).
    yield
    await shutdown_advisor()
    await shutdown_coach()
    await shutdown_budget()
    await shutdown_savings()


app = FastAPI(
    title="Financial Suite",
    version=__version__,
    description=(
        "Enterprise financial-intelligence suite combining four FastAPI "
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
        "split, investment allocation and a savings score.\n\n"
        "Each sub-app exposes its own docs at `/advisor/docs`, `/coach/docs`, "
        "`/budget/docs` and `/savings/docs`."
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


# Mount the isolated sub-applications.
app.mount("/advisor", advisor_app)
app.mount("/coach", coach_app)
app.mount("/budget", budget_app)
app.mount("/savings", savings_app)
