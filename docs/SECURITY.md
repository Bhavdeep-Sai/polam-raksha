# Security Architecture — PolamRaksha (పొలంరక్ష)

> **Status:** Phase 2 Authentication, RBAC, Ownership & Privacy Controls implemented and verified.

---

## Implemented Controls

1. **Argon2id Credential Hashing:** All user passwords and keypad phone PINs are hashed with Argon2id (`argon2-cffi`); plaintext credentials are never persisted.
2. **Short-Lived JWT Access Tokens & Refresh Token Rotation:**
   - Access tokens are short-lived signed JWTs (`HS256`, configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, default 15 minutes) held in memory by browser clients.
   - Refresh tokens are opaque random tokens stored as SHA-256 digests in `refresh_tokens` with `family_id` tracking and delivered in `HttpOnly`, `SameSite=Lax` cookies.
   - Reusing a revoked refresh token triggers automatic revocation of the entire token family (`refresh_token_reused`).
   - Cookie-authenticated `/refresh` and `/logout` requests enforce double-submit CSRF validation (`polam_csrf_token` cookie vs `X-CSRF-Token` header).
3. **Keypad Phone + PIN Rate Limiting:** `POST /api/v1/auth/pin-login` tracks `failed_pin_attempts` and enforces temporary lockout (`pin_locked`, HTTP `429`) after `PIN_MAX_FAILED_ATTEMPTS` failures. Caller ID alone is never accepted as authentication.
4. **Role-Based Access Control (RBAC) & Ownership Isolation:**
   - Roles: `FARMER`, `BUYER`, `OPERATOR`, `ADMIN`.
   - `BUYER` cannot perform farmer actions (`403`).
   - `FARMER` can only access and mutate their own profiles and listings (`403`).
   - `OPERATOR` can assist a farmer only when an active `AssistedAccessRelationship` exists (`403 operator_not_assigned` otherwise).
   - `ADMIN` cannot silently impersonate a farmer on farmer-acting endpoints (`403`).
5. **PII & Location Privacy:** Public listing responses expose only approximate location labels/coordinates; `exact_pickup_address` and farmer contact details are restricted to authorized participants.
6. **Immutable Audit Trail:** Auth events, operator profile views, listing mutations, and token reuse detections are recorded in `audit_events` with `actor_user_id` and `acting_as_farmer_id`.
7. **Database-Level Invariants:** PostgreSQL/SQLAlchemy `CheckConstraint`s reject negative inventory, negative/zero prices, invalid deadlines, and inventory sums exceeding `total_quantity_grams`.
8. **Demo Data Isolation:** `backend/scripts/seed_demo.py` requires explicit opt-in (`--confirm-demo` or `ENABLE_DEMO_SEED=true`) and refuses to run when `APP_ENV=production`.
