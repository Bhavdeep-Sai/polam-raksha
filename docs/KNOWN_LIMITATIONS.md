# Known Limitations & Features Not Implemented — PolamRaksha

## 1. Known Architectural & Operational Limitations
1. **Single-Process WebSocket Fan-Out:** Live auction (`/ws/auctions/{id}`) and notification (`/ws/notifications`) WebSockets poll PostgreSQL outbox/notification tables per backend process. Horizontal multi-instance scaling would require a shared pub/sub bus (intentionally omitted in the modular monolith MVP).
2. **PostgreSQL Concurrency Tests Skipped Locally:** `test_postgresql_concurrent_bids_remain_consistent` requires a live PostgreSQL instance with `polamraksha` credentials and was skipped in the SQLite-backed local test environment.
3. **Playwright E2E Specs Not Run Against Live Servers:** `frontend/tests/e2e/polamraksha.spec.ts` is authored and listed (`2` specs) but requires running PostgreSQL + FastAPI + Vite servers to execute end-to-end.
4. **iOS Safari PWA Constraints:** iOS Safari does not fire `beforeinstallprompt`, suspends WebSockets when backgrounded, and may evict unpinned Cache/localStorage after ~7 days (documented in `docs/PWA.md`).
5. **Frontend Dependency Advisories:** `npm audit` reports advisories on `zod <4.6.6` and `i18next <26.3.4` (major-version upgrades deferred to avoid breaking schema/i18n APIs without full regression testing).

## 2. Features Intentionally Not Implemented (Out of Scope for MVP)
- **Automated Real-Money Payment Gateway / UPI Escrow:** PolamRaksha records buyer commitments and reported payments (`reported_payment_received_paise`), not live banking/UPI settlement.
- **Live Carrier Fleet Dispatch / GPS Tracking:** Transport quotes and routes are estimated via OSRM/cache/Haversine; live truck GPS tracking is not implemented.
- **Multi-Tenant / State-Level Sharding:** Single-database modular monolith suited for district/mandal pilot deployments.
- **Production Readiness Note:** While core domain invariants, security controls, and tests are verified in SQLite/Vitest, PolamRaksha should undergo live PostgreSQL concurrency + Playwright E2E execution in CI/staging before any production rollout.

