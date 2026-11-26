# Architecture — PolamRaksha (పొలంరక్ష)

> **Status:** Phase 3 (Frontend Design System & Application Shell) complete.

---

## 1. System Overview

PolamRaksha is a **modular monolith** designed for transactional consistency, strict privacy isolation, and multi-channel agricultural surplus recovery.

### Technology Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18, TypeScript (strict), Vite 6, Tailwind CSS v4, TanStack Query, i18next (`te`/`en`) |
| API Contract Sync | `openapi-typescript` generated from FastAPI `openapi.json` |
| Backend | FastAPI (Python 3.12, strict type annotations) |
| ORM & Migrations | SQLAlchemy 2, Alembic (`20261126_0001_initial_schema`), `psycopg[binary]` |
| Primary Database | PostgreSQL 16 (only primary datastore) |
| Auth & Security | `pyjwt[crypto]` (short-lived access JWT), `argon2-cffi` (passwords & keypad PINs), HttpOnly refresh cookies + CSRF protection |
| Optimization (ready) | Google OR-Tools CP-SAT |
| Testing & Quality | Pytest, Ruff, Mypy (backend); Vitest, Testing Library, TypeScript, Playwright (frontend) |

---

## 2. Implemented Backend Modules & Schema

### Core & Database
- `backend/app/core/config.py`: Validated Pydantic `Settings` (JWT lifetimes, PIN lockout thresholds, cookie security, CORS).
- `backend/app/core/security.py`: Argon2id hashing/verification (`hash_secret`, `verify_secret`), SHA-256 refresh token hashing, opaque token generation, JWT creation/decoding.
- `backend/app/db/models.py`: Central model registry for Alembic metadata discovery across all 21 normalized tables.

### Normalized Relational Schema (`20261126_0001_initial_schema`)
- **Identity & Access (`users`):** `User` (`FARMER`, `BUYER`, `OPERATOR`, `ADMIN`), `RefreshToken` (family-tracked rotation), `FarmerProfile`, `BuyerProfile`, `AssistedAccessRelationship`.
- **Catalog & Inventory (`listings`):** `CropCatalog`, `ProduceListing` with database-level `CheckConstraint`s preventing negative quantities, invalid prices, invalid deadlines, and ensuring `available_quantity_grams + reserved_quantity_grams + collected_quantity_grams <= total_quantity_grams`.
- **Auctions & Allocation (`auctions`, `allocation`):** `Auction`, `BidRevision`, `AllocationRun`, `Allocation`.
- **Orders & Logistics (`orders`, `logistics`):** `Order`, `CollectionRecord`, `TransportQuote`.
- **Reliability, Channels & System (`reliability`, `notifications`, `ivr`, `system`):** `BuyerReliabilityEvent`, `Notification`, `IvrSession`, `ScheduledJob`, `TransactionalOutboxEvent`, `AuditEvent`, `IdempotencyRecord`.

### Implemented Application Services & Routers
- `backend/app/modules/auth/`: Registration, password login, keypad phone+PIN login with lockout, refresh-token rotation with reuse detection, logout, `/me`, RBAC (`require_roles`), and farmer ownership/assisted-access authorization (`authorize_farmer_access`).
- `backend/app/modules/farmers/`: Private farmer PII profile endpoint (`/api/v1/farmers/{farmer_id}/profile`) restricted to owner farmer or explicitly assigned active operator (with audit logging).
- `backend/app/modules/listings/`: Public approximate-location listing view (`GET /api/v1/listings`) and farmer/assigned-operator listing creation & update (`POST`/`PATCH`).
- `backend/scripts/seed_demo.py`: Explicitly enabled non-production demo seeder with Telugu/English crops and clearly labelled simulated records.

---

## 3. Core Architectural Invariants

- **Single Source of Truth:** All business rules and authorization live in backend application services.
- **Monetary & Quantity Precision:** Integer **paise** for money; integer **grams** for stored quantities.
- **Time Handling:** Timezone-aware **UTC** internally; **IST (`Asia/Kolkata`)** for display.
- **Immutable History:** Bid revisions and audit events are append-only.
- **No Unapproved Infrastructure:** No Redis, Kafka, microservices, Kubernetes, blockchain, or mandatory paid AI services.
