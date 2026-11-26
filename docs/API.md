# API Specification — PolamRaksha (పొలంరక్ష)

> **Status:** Phase 2 (Auth, RBAC, Farmer PII Isolation & Listing Foundation) implemented.

---

## 1. API Conventions

- **Base Prefix:** `/api/v1`
- **OpenAPI Schema:** `GET /api/v1/openapi.json` (`/docs`, `/redoc`)
- **Frontend Type Generation:** Exported via `backend/scripts/export_openapi.py` and compiled into `frontend/src/types/api.ts` with `openapi-typescript`.
- **Error Envelope:**
  ```json
  {
    "error": {
      "code": "string_code",
      "message": "Human-readable safe message",
      "details": {}
    }
  }
  ```
- **Units & Time:** Integer **paise** for currency, integer **grams** for weight, timezone-aware **UTC** ISO-8601 timestamps.

---

## 2. Implemented Endpoints

### System
- `GET /api/v1/health` — Liveness probe.
- `GET /api/v1/ready` — PostgreSQL readiness probe (`SELECT 1`; returns `503` with `database_unavailable` if disconnected).

### Authentication (`/api/v1/auth`)
- `POST /api/v1/auth/register` — Register a `FARMER` or `BUYER` account (`201 Created`).
- `POST /api/v1/auth/login` — Email/phone + password login; returns short-lived Bearer access token and sets HttpOnly `polam_refresh_token` + `polam_csrf_token` cookies.
- `POST /api/v1/auth/pin-login` — Keypad phone + PIN login with failed-attempt lockout (`429 pin_locked`).
- `POST /api/v1/auth/refresh` — Rotates refresh token (enforces `X-CSRF-Token` header for cookie requests; revokes token family on reuse).
- `POST /api/v1/auth/logout` — Revokes refresh token and clears auth cookies.
- `GET /api/v1/auth/me` — Returns authenticated `UserSummary`.

### Farmers (`/api/v1/farmers`)
- `POST /api/v1/farmers/assisted` — Assisted farmer registration by `OPERATOR` with recorded consent (no Aadhaar, bank details, or smartphone required).
- `GET /api/v1/farmers/assisted` — List assigned farmers and assisted action audit history for the authenticated `OPERATOR`.
- `GET /api/v1/farmers/{farmer_id}/profile` — Returns farmer PII (`exact_pickup_address`, `phone_number`) only to the farmer themselves or an explicitly assigned active `OPERATOR` (audited).

### Logistics & Market Reference Prices (`/api/v1/logistics`, `/api/v1/market-prices`)
- `POST /api/v1/logistics/quote` — Compute road/cached/approximate distance, travel estimate, and integer-paise transport economics (`BUYER_PICKUP` leaves farmer-paid cost at `0`).
- `GET /api/v1/logistics/map-points` — Approximate produce coordinates publicly; exact pickup coordinates/address only for owner farmer, assigned operator, or buyer with an order.
- `GET /api/v1/market-prices` — Normalized `paise/kg` reference prices with `is_stale`, `is_simulated`, and non-guarantee disclaimer.
- `POST /api/v1/market-prices/import` — Import CSV or JSON market datasets (`ADMIN`/`OPERATOR`).

### IVR & Voice Accessibility (`/api/v1/ivr`) & Printable Receipts
- `GET /api/v1/ivr/prompts` — Centralized Telugu/English audio prompt catalog & transcripts.
- `POST /api/v1/ivr/sessions` — Start or resume an IVR session (with persisted `draft_json`).
- `POST /api/v1/ivr/sessions/{session_id}/dtmf` — Process keypad DTMF input (`*`, `#`, `0-9`) through the provider-independent state machine (rate-limited PIN auth, duplicate webhook protection).
- `POST /api/v1/ivr/webhooks/{provider}` — HMAC-SHA256 authenticated telephony webhook (`asterisk_sip`, `exotel`).
- `POST /api/v1/ivr/voice/extract` — Structured listing field extraction from voice transcript for read-back confirmation.
- `GET /api/v1/listings/{listing_id}/receipt` — Printable listing receipt for no-phone / assisted farmers.

> **Telephony Channel Status:** The Browser DTMF Simulator and Asterisk/Exotel webhook signature & payload contracts are tested locally. Live cellular calls via Exotel/Indian telecom require KYC, TRAI DLT approval, and paid telephony credits.

### Allocations (`/api/v1/allocations`)
- `POST /api/v1/allocations/auctions/{auction_id}/run` — Execute OR-Tools CP-SAT allocation (`REVENUE_FIRST` or `RESCUE_FIRST`) on latest eligible bids and persist `AllocationRun` snapshot + explanations.
- `POST /api/v1/allocations/{run_id}/approve` — Farmer or assigned operator approves allocation; revalidates inventory & deadlines inside a locked transaction, reserves quantities, and creates `PENDING_CONFIRMATION` orders.
- `GET /api/v1/allocations/auctions/{auction_id}` — List allocation runs and solver explanations for an auction.
- `GET /api/v1/allocations/runs` — Admin monitoring view of recent allocation runs.

### Auctions & Real-Time Bidding (`/api/v1/auctions`, `/ws/auctions`)
- `GET /api/v1/auctions` — List open and closing auctions (sanitized, no buyer/farmer PII).
- `GET /api/v1/auctions/{auction_id}` — Authoritative auction snapshot, server timestamp, active offers, and authenticated buyer's immutable revision history.
- `POST /api/v1/auctions/{auction_id}/bids` — Transactional, idempotent bid placement/revision (`BUYER` only) with `SELECT ... FOR UPDATE`, competitive increment enforcement, soft-close extension, and outbox event persistence.
- `WS /ws/auctions/{auction_id}?token=<jwt>` — Authenticated WebSocket stream sending an immediate `AUCTION_SNAPSHOT` envelope and polling `transactional_outbox_events` (single-process MVP; horizontal multi-instance WS fan-out is not supported without a shared pub/sub layer).
- `GET /api/v1/crops` — Bilingual Telugu/English crop catalog.
- `GET /api/v1/listings` — Public active/partially-allocated listings exposing only approximate locations (no farmer PII).
- `GET /api/v1/listings/mine` — Owner farmer or assigned operator view including inventory breakdown and auction schedule.
- `POST /api/v1/listings/schedule-preview` — Compute feasible bidding, approval, recovery, and collection deadlines from urgency option (`WITHIN_2H`, `WITHIN_6H`, `WITHIN_12H`, `WITHIN_24H`, `CUSTOM`).
- `POST /api/v1/listings` — Create listing & linked auction (`FARMER` owner or assigned `OPERATOR` only; `BUYER` and `ADMIN` forbidden).
- `PATCH /api/v1/listings/{listing_id}` — Update listing with explicit lifecycle transition & committed-inventory lock enforcement.
- `POST /api/v1/listings/{listing_id}/cancel-uncommitted` — Cancel uncommitted `available_quantity_grams` with audit logging while preserving committed quantities.

### Notifications, Admin & Impact Analytics (Phase 9)
- `GET /api/v1/notifications` — List current user's deduplicated notifications (`PENDING`, `DELIVERED`, `FAILED`, `ACKNOWLEDGED`).
- `POST /api/v1/notifications/{notification_id}/acknowledge` — Mark a notification as acknowledged.
- `WS /ws/notifications?token=<jwt>` — Authenticated WebSocket stream for live notification snapshots.
- `GET /api/v1/admin/overview` — Operational monitoring, worker job/outbox counts, and external integration health (`ADMIN` only).
- `GET /api/v1/admin/users` & `PATCH /api/v1/admin/users/{user_id}/status` — User management with audit logging (`ADMIN` only).
- `POST /api/v1/admin/buyers/{buyer_id}/verify` — Buyer verification review with audit logging (`ADMIN` only).
- `GET /api/v1/admin/operator-permissions` & `POST /api/v1/admin/operator-permissions/{relationship_id}/revoke` — Assisted-access governance with audit logging (`ADMIN` only).
- `GET /api/v1/admin/disputes` & `POST /api/v1/admin/disputes/{dispute_id}/resolve` — Dispute review with audit logging (`ADMIN` only).
- `GET /api/v1/admin/audit-events` — Immutable audit event explorer (`ADMIN` only).
- `GET /api/v1/analytics/impact` — IST-aware impact analytics strictly separating production metrics from simulated demo metrics (`ADMIN`/`OPERATOR`).

---

## 3. Planned Endpoint Groups (Phases 3–6)

- **Auctions & Bids:** Auction lifecycle, idempotent bid placement, immutable bid history, `/ws/auctions/{auction_id}`.
- **Allocation & Transport:** OR-Tools CP-SAT multi-buyer & transport-cost-optimized allocations.
- **Orders & Recovery:** Order state transitions, buyer cancellation handling, automatic recovery re-allocation.
- **Analytics & IVR:** Aggregated non-PII analytics and keypad/IVR session workflows.
