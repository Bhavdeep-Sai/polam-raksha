# PolamRaksha Security, Correctness & Test Report

**Date:** 2026-11-26  
**Scope:** Full-stack security review, domain invariant verification, failure-mode testing, performance benchmarking, and E2E test suite authoring.

---

## 1. Security Review & Automated Audits

### Tools Executed
1. **Ruff Security Rules (`ruff check --select S app`):**
   - **Result:** 0 real vulnerabilities across 97 backend Python source files (1 false-positive `S105` on OAuth2 `token_type: Literal["bearer"] = "bearer"` in `app/modules/auth/schemas.py:63`).
   - Confirmed no SQL string interpolation, no `eval`/`exec`/`pickle`, and no hardcoded production secrets.
2. **Frontend XSS & Token Storage Scan (`Select-String`):**
   - **Result:** 0 occurrences of `dangerouslySetInnerHTML` or `innerHTML`.
   - Access tokens are held strictly in memory (`frontend/src/services/api.ts`), never in `localStorage`.
3. **Backend Log Inspection (`Select-String`):**
   - **Result:** No passwords, PINs, or JWTs logged.
4. **NPM Dependency Audit (`npm audit --json`):**
   - **Result:** 12 advisories reported (8 moderate, 2 high, 2 critical; 665 total packages).
     - **Production dependencies:** `zod <4.6.6` (high — DoS via oversized constrained collections, `GHSA-mrhx-c7xc-m3w5`) and `i18next <26.3.4` (moderate — `deepExtend` prototype pollution/DoS, `GHSA-6jcc-5g8w-32mx`).
     - **Dev/Build dependencies:** `vitest` / `@vitest/mocker` / `vite` / `esbuild` / `vite-plugin-pwa` (`glob`/`minimatch`).

### Security & Correctness Fixes Applied During Review
1. **Pydantic Validation Error Serialization Crash (`backend/app/core/errors.py`):**
   - **Finding:** `handle_validation_error` passed `exc.errors()` directly to `JSONResponse`, which raised `TypeError: Object of type ValueError is not JSON serializable` (HTTP 500) whenever a Pydantic `@field_validator` raised a `ValueError`.
   - **Fix:** Wrapped `exc.errors()` with `fastapi.encoders.jsonable_encoder(exc.errors())` and updated status code to `HTTP_422_UNPROCESSABLE_CONTENT`.
2. **Stored XSS Prevention on Listing Photo URLs (`backend/app/modules/listings/schemas.py`):**
   - **Finding:** `CreateListingRequest.photo_urls` accepted arbitrary strings without URL scheme validation (`javascript:` or `data:` payloads).
   - **Fix:** Added `@field_validator("photo_urls")` requiring `http://` or `https://` and max length `<= 500`, verified by `test_unsafe_photo_url_schemes_rejected`.

---

## 2. Tests Executed & Results

### Backend Verification (`backend/`)
- **Pytest (`pytest -v`):** **43 passed, 1 skipped**, 0 failed across 8 test modules:
  - `tests/test_health.py` (5 passed) — health, readiness (connected & 503 DB unavailable), OpenAPI schema, production JWT secret rejection.
  - `tests/test_auth_rbac_schema.py` (8 passed) — Argon2id hashing, PIN lockout, RBAC isolation, operator assisted-access, admin impersonation block, refresh-token rotation + CSRF, DB inventory constraints, demo seeder.
  - `tests/test_farmer_and_assisted_workflows.py` (4 passed) — listing/auction creation, invalid quantities/prices/deadlines, operator consent, committed inventory protection.
  - `tests/test_auction_engine.py` (4 passed, **1 skipped**) — immutable bid revisions, idempotency, soft-close vs hard-close, authenticated WebSockets; **`test_postgresql_concurrent_bids_remain_consistent` was SKIPPED** because local `localhost:5432` rejected default `polamraksha` credentials.
  - `tests/test_allocation_engine.py` (8 passed) — OR-Tools CP-SAT constraints, exhaustive-enumeration parity, greedy fallback, stale-inventory revalidation & approval.
  - `tests/test_ivr_and_voice.py` (4 passed) — keypad registration, order approval via shared service, PIN rate limit & webhook replay, printable receipts.
  - `tests/test_logistics_and_market_prices.py` (4 passed) — transport economics, OSRM fallback to Haversine, quintal-to-kg & staleness, PII location isolation.
  - `tests/test_admin_notifications_analytics.py` (3 passed) — admin RBAC & audit logging, notification outbox deduplication & unconfigured telephone honesty, IST date filtering & demo/production analytics separation.
  - `tests/test_security_invariants_and_benchmarks.py` (3 passed) — unsafe `photo_urls` rejection, speech-unavailable & empty-offer solver failure handling, and workload benchmarks.
- **Alembic PostgreSQL DDL Compilation (`alembic upgrade head --sql`):** Passed cleanly through revision `20261126_0007`.
- **Ruff (`ruff check app tests scripts`):** All checks passed.
- **Mypy (`mypy app tests scripts`):** 0 errors across 98 source files.

### Frontend Verification (`frontend/`)
- **TypeScript (`npm run typecheck`):** Passed (`tsc --noEmit`).
- **Vitest (`npm run test`):** **8 passed** across 2 files (`tests/App.test.tsx`: 5 passed; `tests/PwaOffline.test.tsx`: 3 passed covering offline status/reconnection refresh, local draft retention, and offline bid blocking).
- **Production PWA Build (`npm run build`):** Passed; generated `dist/manifest.webmanifest` and `dist/sw.js` (94 precached entries).
- **Playwright E2E (`frontend/tests/e2e/polamraksha.spec.ts`):** Authored and verified via `npx playwright test --list` (2 E2E specs covering 360px mobile layout and full lifecycle + IVR). **Not executed against live running backend/frontend servers** in this session because local PostgreSQL (`polamraksha` DB) was not provisioned.

---

## 3. Actual Measured Performance Benchmarks

Measured in-process via `test_realistic_workload_benchmarks_and_query_counts` (SQLite-backed `TestClient` + SQLAlchemy `before_cursor_execute` listener, 25 active listings, 20 buyer offers):

| Operation | Measured Latency | SQL Query Count | Notes |
| --- | --- | --- | --- |
| `GET /api/v1/listings` (25 active listings) | **8.68 ms** | **1 query** | Single query, no N+1. |
| `GET /api/v1/analytics/impact` | **37.23 ms** | **5 queries** | Aggregates listings, crops, allocations, orders, collections. |
| `solve_allocation` (CP-SAT, 20 offers, 200 kg) | **16.94 ms** | N/A (in-memory) | Optimal/feasible solution well under 2s solver limit. |

---

## 4. Known Limitations & Remaining Risks

1. **PostgreSQL Concurrency Suite Not Run Against Live Postgres:** `test_postgresql_concurrent_bids_remain_consistent` skipped due to missing local `polamraksha` Postgres credentials. Multi-worker `SKIP LOCKED` and concurrent PostgreSQL row-locking should be executed in CI or `docker compose up postgres` before production deployment.
2. **Playwright Live-Server E2E Not Executed:** E2E specs are written in `frontend/tests/e2e/polamraksha.spec.ts` and listed cleanly, but require running PostgreSQL + FastAPI + Vite dev server to execute end-to-end.
3. **Frontend Dependency Advisories:** `zod` (`<4.6.6`) and `i18next` (`<26.3.4`) have major-version upgrades available to resolve `npm audit` advisories; upgrading them requires testing breaking schema/i18n API changes.
4. **Single-Process WebSockets:** Native WebSockets poll PostgreSQL outbox/notifications per process; horizontal multi-instance scaling would require an external pub/sub layer (out of scope for the modular monolith MVP).

