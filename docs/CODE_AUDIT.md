# PolamRaksha Principal Engineering Code Audit

**Date:** 2026-11-26  
**Scope:** Maintainability, duplication, N+1 query elimination, frontend bundle optimization, and quality gate verification across `backend/` and `frontend/`.

---

## 1. Duplicate Implementations & Bottlenecks Found

### Backend
1. **Repeated Allocation Run Hydration Loop (`backend/app/modules/allocation/service.py`):**
   - `list_runs_for_auction` and `list_all_allocation_runs` both looped over `AllocationRun` rows and issued one `SELECT ... FROM allocations` query per run (`1 + N` queries).
2. **N+1 Profile & User Lookups in Admin Console (`backend/app/modules/admin/service.py`):**
   - `list_admin_users` issued 1 `FarmerProfile` or `BuyerProfile` query per user (`1 + N` queries).
   - `list_operator_permissions` issued 2 `User` queries per relationship (`1 + 2N` queries).
3. **N+1 Auction Lookup in Farmer Listings (`backend/app/modules/listings/router.py`):**
   - `get_my_listings` issued 1 `Auction` query per listing (`1 + N` queries).
4. **N+1 Participant Authorization Lookups in Map Points (`backend/app/modules/logistics/router.py`):**
   - `get_map_points` queried `AssistedAccessRelationship` (for `OPERATOR`) or `Order` (for `BUYER`) inside the listing loop (`1 + N` queries).
5. **Authoritative Single-Source-of-Truth Verification:**
   - Confirmed single authoritative implementations exist for deadline scheduling (`app/modules/listings/deadline_policy.py`), transport economics (`app/modules/logistics/economics.py`), CP-SAT solver (`app/modules/allocation/solver.py`), UTC/IST time helpers (`app/shared/time.py`), centralized notification outbox (`app/modules/notifications/service.py`), and IVR state machine (`app/modules/ivr/state_machine.py`).

### Frontend
1. **Monolithic Main Bundle (`frontend/src/app/App.tsx`):**
   - All role dashboards (`AdminDashboard` with `recharts`, `BuyerDashboard` with `leaflet`, `FarmerDashboard`, `OperatorDashboard`, `IvrSimulatorPage`) were eagerly imported into the root bundle (`1,131.70 kB` JS, triggering Vite's `> 500 kB` chunk size warning).
2. **Vitest / Playwright Glob Overlap (`frontend/vite.config.ts`):**
   - `test` configuration lacked `exclude: ["tests/e2e/**", "node_modules/**"]`, causing `vitest run` to attempt executing `tests/e2e/polamraksha.spec.ts`.

---

## 2. Consolidations & Optimizations Performed

1. **Extracted `_hydrate_allocation_runs()` (`backend/app/modules/allocation/service.py`):**
   - Replaced both `list_runs_for_auction` and `list_all_allocation_runs` N+1 loops with a single shared batch `Allocation.allocation_run_id.in_(run_ids)` query (**2 queries total** regardless of run count).
2. **Batch-Loaded Admin User & Operator Permission Queries (`backend/app/modules/admin/service.py`):**
   - `list_admin_users` now batch-loads `FarmerProfile` and `BuyerProfile` via `.in_(farmer_ids)` / `.in_(buyer_ids)` (**<= 3 queries total** instead of `1 + N`).
   - `list_operator_permissions` now batch-loads all referenced `User` rows in one `.in_(user_ids)` query (**2 queries total** instead of `1 + 2N`).
3. **Batch-Loaded Farmer Listing Auctions (`backend/app/modules/listings/router.py`):**
   - `get_my_listings` now loads all matching `Auction` rows in a single `Auction.listing_id.in_(listing_ids)` query (**2 queries total** instead of `1 + N`).
4. **Batch-Loaded Map Point Authorization Sets (`backend/app/modules/logistics/router.py`):**
   - `get_map_points` now pre-fetches `authorized_farmer_ids` (for `OPERATOR`) and `authorized_listing_ids` (for `BUYER`) in one query before iterating over listings (**<= 2 queries total** instead of `1 + N`).
5. **Route-Level Code Splitting (`frontend/src/app/App.tsx`):**
   - Converted `FarmerDashboard`, `BuyerDashboard`, `OperatorDashboard`, `AdminDashboard`, and `IvrSimulatorPage` to `React.lazy()` with `<Suspense fallback={<LoadingSkeleton rows={4} />}>`.
6. **Excluded Playwright E2E Specs from Vitest (`frontend/vite.config.ts`):**
   - Added `exclude: ["tests/e2e/**", "node_modules/**"]` under `test`.

---

## 3. Removed Dependencies

- **None removed** during this audit: all backend dependencies (`pyproject.toml`) and frontend dependencies (`package.json`) are actively used by implemented modules (`ortools`, `argon2-cffi`, `pyjwt`, `httpx`, `leaflet`, `recharts`, `vite-plugin-pwa`, `react-hook-form`, `zod`, `@tanstack/react-query`, `i18next`).

---

## 4. Measured Before / After Improvements

### Frontend Production Bundle (`vite build`)

| Artifact | Before Lazy Loading | After Lazy Loading | Measured Change |
| --- | --- | --- | --- |
| Main entry `index-*.js` | `1,131.70 kB` (`331.98 kB` gzip) | **`474.79 kB` (`145.27 kB` gzip)** | **-58.0% raw (-56.2% gzip)**; Vite `> 500 kB` warning eliminated |
| `AdminDashboard-*.js` (Recharts) | Bundled in `index.js` | `459.35 kB` (`131.49 kB` gzip) | Loaded on demand for `ADMIN` |
| `BuyerDashboard-*.js` (Leaflet) | Bundled in `index.js` | `163.13 kB` (`48.32 kB` gzip) | Loaded on demand for `BUYER` |
| `FarmerDashboard-*.js` | Bundled in `index.js` | `8.04 kB` (`2.87 kB` gzip) | Loaded on demand for `FARMER` |

---

## 5. Quality Gates Executed

- **Backend Lint (`ruff check app tests scripts`):** Passed (`All checks passed!`).
- **Backend Typecheck (`mypy app tests scripts`):** Passed (`Success: no issues found in 98 source files`).
- **Backend Tests (`pytest -v`):** **43 passed, 1 skipped** (`test_postgresql_concurrent_bids_remain_consistent` skipped without local Postgres `polamraksha` credentials), 0 failed.
- **Frontend Typecheck (`npm run typecheck`):** Passed (`tsc --noEmit`).
- **Frontend Tests (`npm run test`):** Passed (**8/8 tests** across `tests/App.test.tsx` and `tests/PwaOffline.test.tsx`).
- **Frontend Production Build (`npm run build`):** Passed cleanly (`103` PWA precached entries).
- **ESLint / Playwright Live Execution:** ESLint is not configured in `frontend/package.json` (`tsc --noEmit` enforces strict TypeScript checks); Playwright specs in `frontend/tests/e2e/polamraksha.spec.ts` were verified via `npx playwright test --list` (2 specs) and not executed against live servers without a running PostgreSQL instance.

---

## 6. Remaining Intentional Duplication & Limitations

1. **Intentional Client/Server Validation Parity:** Zod schemas on the frontend (`ProduceRegistrationForm.tsx`, `RegisterPage.tsx`) mirror backend Pydantic constraints (`listings/schemas.py`, `auth/schemas.py`) for immediate accessible UX, while backend validation remains authoritative.
2. **Backend Dependency Audit:** `pip-audit` is not installed in the offline virtual environment; `ruff --select S` was executed instead.
3. **Frontend Dependency Advisories:** `npm audit` findings on `zod` and `i18next` remain documented in `docs/TEST_REPORT.md` pending major-version compatibility testing.

