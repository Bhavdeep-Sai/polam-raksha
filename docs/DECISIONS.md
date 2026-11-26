# Architectural Decision Records (ADRs) — PolamRaksha

> **Status:** Initial baseline decisions recorded from Master Project Instructions.

---

## ADR-001: Modular Monolith Architecture
- **Decision:** Build PolamRaksha as a single FastAPI modular monolith paired with a React/TypeScript/Vite SPA and PostgreSQL.
- **Rationale:** Ensures ACID transactions across auctions, allocations, orders, and audit logs without distributed-system complexity. Explicitly avoids microservices, Redis, Kafka, Kubernetes, blockchain, and mandatory paid AI services.

## ADR-002: PostgreSQL as the Only Primary Database
- **Decision:** Use PostgreSQL with SQLAlchemy 2 ORM and Alembic migrations for all persistence, locking, and audit history.
- **Rationale:** Provides strong relational constraints, row-level locking (`SELECT ... FOR UPDATE`) to prevent race conditions and overselling, and transactional integrity for financial and inventory state.

## ADR-003: Integer Units (Paise & Grams) and UTC/IST Time Convention
- **Decision:** Store and compute all monetary values in integer paise and all produce weights in integer grams. Store all timestamps as timezone-aware UTC and render in IST for users.
- **Rationale:** Eliminates floating-point rounding errors in financial and allocation math, and prevents timezone ambiguity in perishable deadline enforcement.

## ADR-004: Google OR-Tools CP-SAT for Constrained Allocation
- **Decision:** Use Google OR-Tools CP-SAT solver for multi-buyer allocation, deadline-aware matching, transportation cost optimization, and cancellation recovery re-allocation.
- **Rationale:** Deterministic, auditable, constraint-driven optimization without relying on AI-generated outputs for financial or allocation calculations.

## ADR-005: Native WebSockets for Real-Time Auction Updates
- **Decision:** Use FastAPI/Starlette native WebSockets for live auction state and bid updates, backed by authoritative PostgreSQL state.
- **Rationale:** Avoids external pub/sub infrastructure (like Redis) while providing low-latency updates to connected clients.

## ADR-006: Multi-Channel Accessibility & Bilingual Support (Telugu & English)
- **Decision:** Support i18next bilingual UI (Telugu and English), large accessible controls, voice guidance, high contrast, keyboard navigation, mobile-first layout, and unified backend services for smartphone, keypad phone, and assisted registration channels.
- **Rationale:** Small and marginal farmers have diverse device access and literacy/language needs; all channels must share one authoritative backend service layer.

## ADR-007: Security, Immutability, and Provider Interfaces
- **Decision:** Enforce JWT + Argon2 authentication, RBAC, ownership validation, rate limiting, restricted CORS, immutable bid/audit logs, and provider interfaces with local fallbacks for optional external integrations.
- **Rationale:** Protects farmer PII, prevents replay/duplicate-bid/overselling attacks, and guarantees offline/local resilience.

