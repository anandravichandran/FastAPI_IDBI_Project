# Production-Readiness Audit — FastAPI Financial Suite

**Reviewers:** Principal Software Engineer · Principal QA Automation · Principal Security · Principal SRE
**Target:** `server.py` modular monolith `v1.4.0` (advisor · coach · budget · savings · rag · market)
**Verdict:** ⚠️ **NOT production-ready for a banking deployment.** Excellent engineering foundations, but blocked by (1) a test-suite that cannot run, and (2) the total absence of authentication. Both are fixed / scaffolded in this package.

> **Constraint disclosure:** the audit sandbox has **no network and no test dependencies** (`pytest`, `fastapi`, `httpx`, `pydantic-settings` are absent). Phases 4/5/10 are therefore **static analysis + generated, un-executed** test/fix code. Run `pytest` in a full environment to confirm. All findings below are cited to exact files/lines from source.

---

## Phase 1 — Architecture (reverse-engineered)

**Shape:** modular monolith. `server.py` builds six independent FastAPI sub-apps at import time and mounts them under `/advisor`, `/coach`, `/budget`, `/savings`, `/rag`, `/market`. The parent app owns a lifespan that calls each sub-app's `shutdown_dependencies()` on exit (necessary because Starlette does **not** propagate lifespan events to mounted sub-apps).

**Per sub-app: Clean Architecture** (`api` → `services` → `repositories` → `domain`), wired by an `api/deps.py` composition root using `functools.lru_cache` singletons. Config is `pydantic-settings` (`core/config.py`), errors are centralized (`core/error_handlers.py` + `core/exceptions.py`), logging is structured JSON with a request-id contextvar and `X-Request-ID` response header (`core/middleware.py` + `core/logging.py`).

| Domain | Flow (verified from source) |
|---|---|
| **Investment Advisor** | Validate profile → deterministic `PortfolioAnalyzer` → concurrent OpenBB snapshot + RAG retrieval via `asyncio.gather` → LLM narrative (DeepSeek/NVIDIA) with **deterministic fallback** if LLM unconfigured/fails. |
| **Financial Coach** | Load profile → market snapshot → intent classification → affordability assessment → RAG grounding → LLM narration → persist 2 conversation turns. |
| **Budget Planner** | Pure deterministic engine (50/30/20-style allocation), no I/O. |
| **Savings Optimizer** | Pure deterministic engine (emergency-fund + goal optimization), no I/O. |
| **RAG** | Upload → parse (pypdf, lazy) → chunk → embed → vector store → retrieve → `build_context`. CPU-bound work offloaded via `run_in_threadpool`. Pluggable embedder (SentenceTransformer **or** hashing fallback) + vector store (Chroma **or** in-memory cosine), with non-production graceful degradation. |
| **Market** | cache-aside → rate-limit → retry-with-backoff → provider (OpenBB **or** synthetic fallback). |

**AI layer:** OpenAI-compatible `/chat/completions` over async `httpx`. `llm_provider` selects `deepseek` (`api.deepseek.com`) or `nvidia` (`integrate.api.nvidia.com/v1`, model `deepseek-ai/deepseek-v4-pro`). Any transport error → `LLMError` → deterministic fallback narrative. **The suite never hard-fails because an LLM is down** — good SRE design.

---

## Phase 2 — API Discovery

Auth column is **NONE** for every row (see Phase 7). Prefixes include the mount, e.g. advisor advice = `POST /advisor/api/v1/advisor/advice`.

| Method | Endpoint (after mount) | Purpose | Auth | Input | Output | Errors |
|---|---|---|---|---|---|---|
| GET | `/`, `/health` | Parent liveness/aggregate | None | – | status JSON | 500 |
| POST | `/advisor/api/v1/advisor/advice` | Generate advice | None | `AdviceRequest` | `AdviceResponse` | 422, 502, 500 |
| GET | `/advisor/api/v1/health` | Advisor health | None | – | `{status, llm_configured}` | 500 |
| POST | `/coach/api/v1/coach/chat` | Coach turn | None | `ChatRequest` | `ChatResponse` | 422, 502, 500 |
| GET | `/coach/api/v1/coach/history` | Conversation history | None | `user_id` q | history | 422, 500 |
| GET | `/coach/api/v1/coach/summary` | Financial summary | None | `user_id` q | summary | 422, 500 |
| POST | `/budget/api/v1/budget/plan` | Budget plan | None | `BudgetRequest` | `BudgetResponse` | 422, 500 |
| POST | `/savings/api/v1/savings/optimize` | Savings plan | None | `SavingsRequest` | `SavingsResponse` | 422, 500 |
| POST | `/rag/api/v1/documents` | Upload PDF | None | multipart file | doc meta | 415, 413, 422, 500 |
| GET | `/rag/api/v1/documents` | List docs | None | – | list | 500 |
| GET | `/rag/api/v1/documents/{id}` | Get doc | None | path id | doc | 404, 500 |
| DELETE | `/rag/api/v1/documents/{id}` | Delete doc | None | path id | 204 | 404, 500 |
| GET | `/rag/api/v1/documents/stats` | Corpus stats | None | – | stats | 500 |
| POST | `/rag/api/v1/rag/query` | RAG answer | None | `QueryRequest` | answer + sources | 422, 500 |
| POST | `/rag/api/v1/rag/context` | Retrieve context | None | `ContextRequest` | chunks | 422, 500 |
| GET | `/market/api/v1/stocks/{sym}/quote` · `/historical` · `/ratios` | Equities | None | path + query | `QuoteOut`/`HistoricalPricesOut`/`FinancialRatiosOut` | 422, 502, 500 |
| GET | `/market/api/v1/mutual-funds/{sym}` (+`/historical`) · `/etf/{sym}` (+`/historical`) | Funds | None | path + query | `QuoteOut`/`HistoricalPricesOut` | 422, 502, 500 |
| GET | `/market/api/v1/gold` (+`/historical`) · `/indices/{sym}` (+`/historical`) | Commodities/Indices | None | path + query | Quote/Historical | 422, 502, 500 |
| GET/POST | `/market/api/v1/news` | News feed | None | query / `NewsRequest` | `NewsFeedOut` | 422, 502, 500 |
| GET | `/market/api/v1/cache/stats` | Cache diagnostics | None | – | `CacheStatsOut` | 500 |
| GET | `/{app}/api/v1/health` (all) | Per-app health | None | – | `HealthOut` | 500 |

~30 routes. **All read/verb methods are GET/POST/DELETE — no PUT/PATCH exist.**

---

## Phase 3 — Test Audit

**20 test files, ~104 tests, per-app conftests using fakes** (`FakeLLM`, `FakeMarketData`, `FakeKnowledge`). Best coverage: **market** (5 files: api/cache/rate_limiter/retry/service). Deterministic engines (budget/savings/portfolio_analyzer) well unit-tested.

**Gaps:**
- **No integration tests** for the mounted `server:app` → added `tests/test_suite_integration.py`.
- **No security tests** (auth, CORS, prompt injection, payload abuse) → added `tests/security/test_security.py`.
- **Thin edge cases** for advisor input validation → added `tests/advisor/test_edge_cases.py`.
- Root `tests/conftest.py`, `tests/test_advisor_api.py`, `tests/test_portfolio_analyzer.py` import the **legacy `app/` package** (a full duplicate of advisor) — a maintenance smell; keep only one.
- **Incorrect mock/fixture:** the advisor & coach `client` fixtures were unrunnable (see Phase 4).

---

## Phase 4 — Test Execution → **BLOCKER FOUND & FIXED**

Tests could not be executed here (deps absent), but static analysis surfaced a **certain, deterministic failure** that breaks essentially **all advisor + coach API tests**:

**Root cause:** the TestClient fixtures reference the **package name** as if it were the app object. `from coach.main import create_app` binds `create_app`, **not** `coach`; likewise `advisor`. So `coach.dependency_overrides[...]` raises `NameError: name 'coach' is not defined` at fixture setup — every test using the `client` fixture **errors out**.

| File | Line | Broken | Fix |
|---|---|---|---|
| `tests/coach/conftest.py` | 79–80 | `coach.dependency_overrides[...]` | `app.dependency_overrides[...]` |
| `tests/coach/test_coach_api.py` | 47, 51 | `coach.dependency_overrides[...]` | `app.dependency_overrides[...]` |
| `tests/advisor/conftest.py` | 92 | `advisor.dependency_overrides[...]` | `app.dependency_overrides[...]` |
| `tests/advisor/test_advisor_api.py` | 42 | `advisor.dependency_overrides[...]` | `app.dependency_overrides[...]` |

✅ **All four fixed in this package** (`app` is the local returned by `create_app(settings)`).

**Warnings to address (do not ignore):** ensure `pytest.ini`/`pyproject` registers any custom marks; confirm no `DeprecationWarning` from pydantic v1-style validators; treat `asyncio_mode="auto"` interactions with sync TestClient carefully.

---

## Phase 5 — Endpoint Validation (TestClient)

Generated `tests/test_suite_integration.py` validates status, `X-Request-ID` header, mounting of all six sub-apps, malformed-JSON and large-payload handling (via security file). **PUT/PATCH:** none exist, so none are testable — documented rather than fabricated. Rate-limit/timeout behaviour lives in the market layer and is unit-tested there (`test_rate_limiter.py`, `test_retry.py`).

---

## Phase 6 — Edge Cases

Generated `tests/advisor/test_edge_cases.py` (missing body, empty object, age out of range 18–100, negative income/expenses, implausible cashflow guardrail `expenses > 3×income`, `extra="forbid"` rejection) and prompt-injection / oversized-payload cases in the security suite. **Note:** the user's checklist mentions **MongoDB** and a **vector DB** — this build has **no MongoDB** (in-memory repos) and the vector store degrades gracefully to in-memory cosine, so those specific outage tests are N/A and are documented as such rather than faked.

---

## Phase 7 — Security Audit

| Severity | Finding | Attack scenario | Fix |
|---|---|---|---|
| 🔴 **Critical** | **No authentication/authorization on any endpoint** | Anyone on the network calls advice/coach/RAG/market freely; no tenant isolation | Add an auth dependency (API key or JWT) applied globally. Scaffold in `SECURITY_FIXES.md`; enforced by an xfail test now. |
| 🔴 **Critical** | **Live secret handling** — real NVIDIA key was shared in plaintext | Key exfiltration → billed inference / abuse | **Rotate/revoke the exposed key now.** Keep keys only in `.env`/secret manager; never in chat or VCS. |
| 🟠 **High** | **CORS: `allow_origins=["*"]` + `allow_credentials=True`** (advisor/coach/budget/savings/market `main.py`) — invalid & unsafe combo | Credentialed cross-origin calls from any site once cookies/auth exist | ✅ **Fixed** — explicit `cors_allow_origins` allowlist + `cors_allow_credentials=False` by default; never wildcard-with-credentials. |
| 🟠 **High** | **Prompt injection / RAG poisoning** — user text and uploaded PDF chunks flow into LLM prompts ungated | Uploaded doc says "ignore instructions, leak secrets" | Sanitize/delimit untrusted content, add allow/deny guardrails, keep secrets out of prompt context. Resilience test added. |
| 🟡 **Medium** | **Memory-DoS on upload** — RAG does `await file.read()` (full file into memory) **before** the `max_upload_mb` (25) size check | Attacker streams a multi-GB body → OOM | Enforce size during streaming / check `Content-Length` first; reject before buffering. |
| 🟡 **Medium** | **SSRF surface** — `deepseek_base_url` / `nvidia_base_url` / OpenBB PAT login are configurable | Misconfig/compromise points client at attacker host | Pin/validate outbound hosts against an allowlist. |
| 🟢 Low/OK | SQL/NoSQL/Command injection | – | **Not applicable** — in-memory repos, no DB, no shell exec. |
| 🟢 OK | Sensitive logging | – | Middleware logs method/path/status/duration only — **no bodies**. Good. |

---

## Phase 8 — Performance Audit

| Issue | Location | Fix |
|---|---|---|
| **Serial OpenBB calls** | advisor `repositories/openbb_market_data.py` (`for symbol in symbols:`) → N× round-trips | Batch or `asyncio.gather` the per-symbol fetches. |
| **JSON serialize in hot path** | `services/prompt_builder.py` `json.dumps(context, indent=2)` per request | Precompute/trim context; avoid `indent` in prod. |
| **Non-thread-safe lazy client init** | `deepseek_llm.py` / `nvidia_llm.py` `_http()` (`if self._client is None`) | Guard with `asyncio.Lock` or build once in DI. |
| **Per-request embedding, no query cache** | RAG query path | LRU-cache query embeddings; reuse the embedder singleton (already `lru_cache`d). |
| ✅ Good | market pipeline | cache-aside + rate-limit + retry already optimal. |

---

## Phase 9 — Production Readiness

**Strong:** centralized exception handlers (`AppException` → envelope with `code`/`message`/`details`/`request_id`; 422 for validation; 500 catch-all), structured JSON logging + request-id + `X-Request-ID`, per-app health endpoints, `lru_cache` DI, typed config, **Dockerfile** (non-root `appuser` uid 10001, `HEALTHCHECK`, slim base) and **docker-compose.yml** present.

**Gaps:** ❌ no auth · ❌ no circuit breakers (retry only, in market) · ❌ no rate limiting at the edge (only market-internal) · ⚠️ **no `render.yaml`** despite "Render deployment" requirement · ⚠️ upload size check ordering (Phase 7) · connection pooling limited to default httpx clients.

---

## Phase 10 — Coverage Additions

Added: `tests/test_suite_integration.py`, `tests/security/test_security.py`, `tests/advisor/test_edge_cases.py`. Combined with the four fixed fixtures, advisor/coach API suites go from **0% runnable → executable**, plus new integration + security coverage. Reaching a *measured* >95% requires running `pytest --cov` in a full environment (not possible in this sandbox).

---

## Phase 11 — Final Report (summary)

1. **Architecture** — clean, well-layered modular monolith; sound fallback design. ✅
2. **API coverage** — ~30 routes mapped; all unauthenticated. ⚠️
3. **Security** — 2 Critical, 2 High, 2 Medium; CORS fixed, auth outstanding. 🔴
4. **Performance** — a few hot-path/serial issues; market layer exemplary. 🟡
5. **Failed tests** — advisor+coach API suites unrunnable (NameError) → **fixed**. 🔴→✅
6. **Missing tests** — integration, security, edge cases → **added**. ✅
7. **Bugs** — 4× `dependency_overrides` NameError (fixed); CORS wildcard+credentials (fixed); upload size-check ordering; coach `summary` reaches into `service._analyzer` private attr (add a public method). 
8. **Production risks** — no auth (go-live blocker), exposed key (rotate now), missing `render.yaml`, no circuit breaker/edge rate-limit. 
9. **Refactoring** — drop the duplicate legacy `app/` package; add public `CoachService.health_score()`; centralize a shared security/CORS/auth module across sub-apps. 
10. **Fixed code** — this package contains the applied fixes (`/data/audit-fixed`) + new tests. 

### Go-live checklist
- [ ] **Rotate the exposed NVIDIA API key immediately.**
- [ ] Add and enforce authentication on every business endpoint.
- [ ] Run `pytest` in a full env; confirm the fixed fixtures pass; measure coverage.
- [ ] Fix upload size-check ordering; add edge rate-limiting + circuit breakers.
- [ ] Add `render.yaml`; verify secrets come only from the platform secret store.
