# Financial Suite

An enterprise financial-intelligence platform that combines **four FastAPI
microservices** behind a single gateway:

| Sub-app | Mount | What it does |
|---|---|---|
| **Investment Advisor** | `/advisor` | Portfolio analysis, risk scoring, target asset allocation, SIP & emergency-fund recommendations, diversification advice — grounded in **OpenBB** market data, **RAG** knowledge and **DeepSeek V3**. |
| **Financial Coach** | `/coach` | Conversational, avatar-ready coaching (“Can I buy a car?”, “Should I increase SIP?”, “Can I afford a home loan?”, “Am I overspending?”, “How can I improve savings?”) over the customer's transactions, budget, savings and goals — grounded in **RAG** and **DeepSeek V3**. |
| **Budget Planner** | `/budget` | Turns **income, expenses, bills and goals** into a recommended monthly budget (50/30/20), expense breakdown, savings percentage, alerts, overspending detection and a budget score/grade. Fully **deterministic** — no LLM or network I/O. |
| **Savings Optimizer** | `/savings` | Turns **salary, expenses, loans, savings and goals** into a recommended **emergency fund**, **monthly saving** and an actionable **SIP / fixed-deposit / liquid-fund** split, with full investment allocation, goal projections, alerts and a savings score/grade. Fully **deterministic** — no LLM or network I/O. |

## Design: a modular monolith

The services were built independently, each as a self-contained
**Clean Architecture** application (API → Services → Domain ports ←
Repositories). Rather than force them into a single tangled codebase, the
suite mounts them as **isolated ASGI sub-applications**:

```
                           server.py  (FastAPI gateway)
                          │  lifespan releases each app's resources
     ┌────────────┬────────────┴─────────────┬────────────┐
mount /advisor  mount /coach            mount /budget  mount /savings
     │              │                         │              │
advisor/        coach/                   budget/        savings/
 (package)       (package)                (package)      (package)
  api/            api/                     api/           api/
  services/       services/                services/      services/
  domain/ ←ports→ domain/ ←ports→          domain/         domain/
  repositories/   repositories/            (pure engine)  (pure engine)
  core/ (config, logging, exceptions, middleware) × each
```

Each sub-app keeps its **own** configuration, structured logging, middleware,
centralized exception handling, dependency-injection composition root and
OpenAPI docs. Benefits:

- **Isolation** — a change or failure in one app can't corrupt the others; they
  share no mutable module state.
- **Independent evolution** — each app can still run standalone
  (`uvicorn advisor.main:app` / `uvicorn coach.main:app` /
  `uvicorn budget.main:app` / `uvicorn savings.main:app`).
- **One deployment** — a single image, port, health probe and (where relevant)
  DeepSeek key serve all four.

The packages are namespaced (`advisor.*`, `coach.*`, `budget.*`, `savings.*`)
precisely so all four can be imported into the same Python process without
module-name collisions.

## Folder layout

```
financial-suite/
├─ server.py                 # gateway: mounts /advisor, /coach, /budget, /savings
├─ advisor/                  # Investment Advisor (Clean Architecture package)
│  └─ main.py  api/  services/  domain/  repositories/  schemas/  core/
├─ coach/                    # Financial Coach (Clean Architecture package)
│  └─ main.py  api/  services/  domain/  repositories/  schemas/  core/
├─ budget/                   # Budget Planner (Clean Architecture package)
│  └─ main.py  api/  services/  domain/  schemas/  core/
├─ savings/                  # Savings Optimizer (Clean Architecture package)
│  └─ main.py  api/  services/  domain/  schemas/  core/
├─ tests/
│  ├─ advisor/   ├─ coach/   ├─ budget/   └─ savings/
├─ requirements.txt  requirements-dev.txt
├─ Dockerfile  docker-compose.yml  Makefile  pyproject.toml
└─ .env.example  .gitignore  README.md
```

### Savings Optimizer internals

```
savings/
├─ main.py                        # app factory (create_app) + ASGI app
├─ api/
│  ├─ deps.py                     # DI composition root (get_optimizer)
│  └─ v1/{savings,health}.py      # thin controllers
├─ services/savings_optimizer.py  # the deterministic optimization engine
├─ domain/{entities,enums}.py     # framework-free value objects + rules
├─ schemas/{request,response}.py  # Pydantic DTOs + domain mapping
└─ core/{config,exceptions,logging,middleware,error_handlers}.py
```

## Route map

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/` | Suite metadata + links |
| `GET`  | `/health` | Aggregate liveness probe |
| `GET`  | `/docs` | Gateway OpenAPI docs |
| `POST` | `/advisor/api/v1/advisor` | Generate investment advice |
| `GET`  | `/advisor/docs` | **Advisor** OpenAPI docs |
| `POST` | `/coach/api/v1/coach/chat` | Ask the coach a money question |
| `GET`  | `/coach/api/v1/coach/history` | Conversation history |
| `GET`  | `/coach/api/v1/coach/summary` | Financial-health summary |
| `GET`  | `/coach/docs` | **Coach** OpenAPI docs |
| `POST` | `/budget/api/v1/budget/plan` | Generate a monthly budget plan |
| `GET`  | `/budget/docs` | **Budget** OpenAPI docs |
| `POST` | `/savings/api/v1/savings/optimize` | Optimize savings & investment allocation |
| `GET`  | `/savings/api/v1/health` | Savings health |
| `GET`  | `/savings/docs` | **Savings** OpenAPI docs |

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optionally add DEEPSEEK_API_KEY (powers advisor + coach)
uvicorn server:app --reload   # → http://localhost:8000
```

Then open:

- **http://localhost:8000/docs** — gateway
- **http://localhost:8000/advisor/docs** — Investment Advisor
- **http://localhost:8000/coach/docs** — Financial Coach
- **http://localhost:8000/budget/docs** — Budget Planner
- **http://localhost:8000/savings/docs** — Savings Optimizer

```bash
# Savings Optimizer — salary, expenses, loans, savings, goals → full plan:
curl -s http://localhost:8000/savings/api/v1/savings/optimize \
  -H 'Content-Type: application/json' \
  -d '{
    "currency": "INR",
    "monthly_salary": 220000,
    "monthly_expenses": 95000,
    "current_savings": 300000,
    "risk_profile": "moderate",
    "loans": [
      {"name": "Car Loan", "emi": 16000, "outstanding": 480000,
       "interest_rate_pct": 9.5, "months_remaining": 36}
    ],
    "goals": [
      {"name": "Emergency Fund", "target_amount": 800000, "saved_amount": 300000,
       "horizon_months": 12, "priority": "high"},
      {"name": "Child Education", "target_amount": 2500000, "saved_amount": 200000,
       "horizon_months": 120, "priority": "medium"}
    ]
  }' | jq

# Budget Planner — income, expenses, bills, goals → monthly plan:
curl -s http://localhost:8000/budget/api/v1/budget/plan \
  -H 'Content-Type: application/json' \
  -d '{"currency":"INR","incomes":[{"name":"Salary","amount":220000,"frequency":"monthly"}],
       "expenses":[{"category":"groceries","amount":18000}],
       "bills":[{"name":"Rent","amount":45000,"category":"housing","due_day":5}],
       "goals":[{"name":"Emergency Fund","target_amount":600000,"saved_amount":150000,"months_remaining":18,"priority":"high"}]}' | jq

# Coach (seed customer cust-001 — Ada Lovelace — is preloaded):
curl -s http://localhost:8000/coach/api/v1/coach/chat \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"cust-001","message":"Can I buy a car worth 12 lakh?"}' | jq

# Advisor: see /advisor/docs for the full request schema.
```

### What the Savings Optimizer returns

`POST /savings/api/v1/savings/optimize` responds with:

- **`emergency_fund`** — target (N months of expenses + EMIs), current coverage,
  months covered, shortfall, a suggested monthly top-up and a status
  (`underfunded` / `on_track` / `fully_funded`).
- **`recommended_monthly_saving`** — investable surplus after expenses & EMIs,
  plus **`savings_rate_pct`** and **`foir_pct`** (loan-EMI-to-income ratio).
- **`recommended_sip`**, **`recommended_fixed_deposit`**, **`recommended_liquid_fund`**
  — the monthly amount for each instrument.
- **`investment_allocation`** — the full percentage + amount split across SIP /
  FD / liquid, each with a rationale. A waterfall biases toward liquid while the
  emergency fund is short, then to a risk-based growth mix, nudged by goal
  horizons.
- **`goals`** — per-goal required vs funded monthly, progress and on-track flag
  (funded by priority after the emergency-fund top-up).
- **`alerts`** — leveled (info/warning/critical) signals: no surplus, low savings
  rate, high debt burden, emergency-fund gaps and underfunded goals.
- **`savings_score`** (0–100) & **`grade`** (A–E) — an explainable composite of
  savings rate, emergency-fund coverage, debt burden and goal-funding readiness.
- **`highlights`** / **`recommendations`** — plain-language next steps.

### What the Budget Planner returns

`POST /budget/api/v1/budget/plan` responds with a recommended 50/30/20 budget,
needs/wants/savings buckets, a category-level `expense_breakdown`, `savings_pct`,
`overspending`, leveled `alerts`, per-goal funding, and a `budget_score` /
`grade`.

## Configuration

All sub-apps read the same process environment (see `.env.example`). Shared
keys — `LOG_LEVEL`, `LOG_JSON`, `ENVIRONMENT`, `API_V1_PREFIX` — apply to all;
`DEEPSEEK_*` / `RAG_TOP_K` power the advisor and coach; the Budget Planner adds
its own `*_TARGET_PCT` and alert thresholds; the Savings Optimizer adds
`EMERGENCY_FUND_MONTHS`, allocation presets and horizon thresholds
(`HEALTHY_SAVINGS_RATE_PCT` / `MAX_FOIR_PCT` are shared with the coach). A single
DeepSeek key powers the whole suite.

> `APP_NAME` is intentionally left unset so each sub-app keeps its own default
> title. Setting it would rename all of them.

## Shared design principles

- **The numbers are deterministic; any model only explains them.** Every risk
  score, allocation, EMI, FOIR, budget envelope, emergency fund and grade is
  computed by auditable, unit-tested engines. The Budget Planner and Savings
  Optimizer use **no** LLM at all; the advisor and coach use DeepSeek V3 only to
  narrate figures it may not invent or alter.
- **Resilient by default.** With no API key or during a DeepSeek outage, the
  advisor and coach fall back to deterministic narration; the budget and savings
  engines never depend on the network.
- **Ports & adapters.** Market data (OpenBB), knowledge (RAG) and history sit
  behind interfaces; swap in a real vector DB, core-banking API or Redis store
  by editing only each app's `api/deps.py`.

## Testing

```bash
pip install -r requirements-dev.txt
pytest                # all suites
pytest tests/savings  # or one at a time
```

Tests run fully offline: DeepSeek is replaced by a fake, repositories are
in-memory, and the budget & savings engines are pure — no network or API key
required.

## Docker

```bash
docker compose up --build   # serves the whole suite on :8000
```

## Disclaimer

All services produce **educational information** derived from the provided
financial data, not personalized or regulated financial advice.
