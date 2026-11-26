# AGENTS.md — PolamRaksha (పొలంరక్ష)

**Tagline:** Save the Harvest. Secure the Farmer's Future.
**Telugu Tagline:** పంటకు రక్షణ, రైతుకు భరోసా.

> **Mandatory Pre-Task Rule:** Read `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/API.md`, and `docs/PROGRESS.md` before every subsequent development task.

---

## 1. Product Vision

PolamRaksha helps small and marginal farmers sell unsold perishable agricultural produce through accessible registration, real-time competitive auctions, deadline-aware buyer matching, multi-buyer allocation, transportation cost optimization, and automatic recovery from buyer cancellations.

- The product must serve farmers with **smartphones**, **ordinary keypad phones**, and **no personal digital devices** (via assisted registration).
- The application must be usable in **Telugu** and **English**.

---

## 2. Mandatory Architecture

Use a **modular monolith** architecture with:

- **Frontend:** React, TypeScript, and Vite
- **UI & Styling:** Tailwind CSS and shadcn/ui design system
- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL as the only primary database
- **ORM & Migrations:** SQLAlchemy 2 ORM and Alembic migrations
- **Authentication:** JWT authentication with Argon2 password hashing
- **Real-time:** Native WebSockets for real-time auction updates
- **Optimization:** Google OR-Tools CP-SAT for constrained allocation
- **Frontend State & Forms:** TanStack Query for server-state management; React Hook Form and Zod for frontend forms
- **i18n, Maps & Charts:** i18next for internationalization; Leaflet for maps; Recharts for analytics
- **Local Dev & Testing:** Docker Compose for local development; Pytest, Vitest, and Playwright for testing

**Prohibited technologies:** Do not introduce unnecessary microservices, Redis, Kafka, Kubernetes, blockchain, or mandatory paid AI services.

---

## 3. Non-Negotiable Engineering Principles

1. Follow DRY, KISS, YAGNI, separation of concerns, and appropriate SOLID principles.
2. Never duplicate existing components, functions, services, API clients, schemas, or business rules.
3. Before creating anything, search the repository for existing implementations.
4. Extend existing modules rather than generating parallel versions.
5. Maintain one authoritative implementation of each business rule.
6. All channels must use the same application services.
7. Never implement authoritative business logic inside React components.
8. Never trust client-side prices, timestamps, user roles, or inventory values.
9. Never hardcode secrets, user credentials, market prices, or production endpoints.
10. Use environment variables with validated configuration.
11. Use strict TypeScript and Python type annotations.
12. Avoid unnecessary abstractions and generic frameworks.
13. Use database transactions for critical operations.
14. Use explicit state machines for auctions and orders.
15. Use **integer paise** for money and **integer grams** for stored quantities.
16. Use **timezone-aware UTC timestamps** internally and **IST** for display.
17. Validate all inputs at API and database boundaries.
18. Maintain immutable bid and audit histories.
19. Never silently swallow errors.
20. Provide meaningful loading, empty, error, and offline states.
21. Do not claim an operation succeeded before the backend confirms it.
22. Never present simulated data as real-world results.
23. Never use AI-generated outputs as authoritative financial calculations.
24. Keep external integrations behind provider interfaces.
25. Every optional external integration must have a local fallback or graceful unavailable state.

---

## 4. Security

- Implement role-based access control (RBAC), ownership validation, secure password hashing (Argon2), rate limiting, input validation, restricted CORS, secure token handling, audit logging, and safe error responses.
- Prevent race conditions, duplicate bids, overselling, unauthorized actions, and replayed requests.
- Never expose farmers' personal information to unauthorized users.

---

## 5. Accessibility

- Use large controls, Telugu translations, voice guidance, high contrast, keyboard navigation, and mobile-first layouts.
- Do not rely exclusively on colors, icons, or text.
- Support assisted registration for farmers without phones.

---

## 6. Development Workflow

Before each implementation:

1. Inspect the existing repository.
2. Identify affected modules and reusable implementations.
3. Write a concise implementation plan.
4. Identify database migrations and API contract changes.
5. Implement only the requested phase.
6. Run relevant tests, linting, and type checks.
7. Fix failures before reporting completion.
8. Update project documentation.

**Strict Prohibitions:**
- Never delete working functionality without a justified migration plan.
- Never rewrite the entire project unnecessarily.
- Never use destructive terminal commands, reset databases, delete user data, push credentials, or deploy publicly without explicit approval.

---

## 7. Definition of Done

A feature is complete only when:

- The backend logic is implemented.
- Required database constraints are present.
- Frontend integration uses actual APIs.
- Error cases are handled.
- Authorization is enforced.
- Relevant automated tests pass.
- Documentation is updated.
- No duplicate implementation exists.
- Any limitations are explicitly documented.

