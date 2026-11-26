# PolamRaksha (పొలంరక్ష)

**Save the Harvest. Secure the Farmer's Future.**  
**పంటకు రక్షణ, రైతుకు భరోసా.**

PolamRaksha is a modular-monolith agricultural surplus recovery platform helping small and marginal farmers sell unsold perishable produce through accessible smartphone, keypad IVR, and operator-assisted workflows, real-time competitive auctions, OR-Tools CP-SAT multi-buyer allocation, transport cost optimization, and automatic cancellation recovery.

---

## Architecture Overview

```text
  [Smartphone PWA / Desktop SPA]    [Keypad Phone / Browser IVR Simulator]
               \                                    /
                v                                  v
        +--------------------------------------------------+
        |         FastAPI Modular Monolith (REST + WS)     |
        |  Auth/RBAC | Listings | Auctions | CP-SAT Solver |
        |  Orders/Recovery | IVR | Logistics | Analytics   |
        +--------------------------------------------------+
                   |                            |
                   v                            v
          [PostgreSQL 16]              [Background Worker]
        (Row Locks, Outbox,           (Auction Close, Jobs,
         Audit & Constraints)          Outbox Notifications)
```

---

## Quick Start (Primary Local Demo Environment)

### Option A: Docker Compose (Recommended)
```bash
cp .env.example .env
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/seed_demo.py --confirm-demo
```

### Option B: Native Development
```bash
# 1. Backend setup & migration
cd backend
uv sync --python 3.12
uv run alembic upgrade head
uv run python scripts/seed_demo.py --confirm-demo

# 2. Start FastAPI backend & background worker (separate terminals)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
uv run python -m app.workers.runner

# 3. Frontend setup & dev server
cd ../frontend
npm install
npm run dev
```

### Verification Endpoints
- **Frontend PWA:** `http://localhost:5173`
- **Backend Health:** `http://localhost:8000/api/v1/health`
- **Database Readiness:** `http://localhost:8000/api/v1/ready`
- **OpenAPI Docs:** `http://localhost:8000/docs`

---

## Demo Credentials (Simulated Non-Production Data Only)

| Role | Email | Password | Keypad PIN |
| --- | --- | --- | --- |
| **Admin** | `demo.admin@polamraksha.local` | `DemoAdmin#2026` | — |
| **Farmer 1** | `demo.farmer1@polamraksha.local` | `DemoFarmer#2026` | `1234` |
| **Operator** | `demo.operator1@polamraksha.local` | `DemoOperator#2026` | — |
| **Buyer 1** | `demo.buyer1@polamraksha.local` | `DemoBuyer#2026` | — |

---

## Running Tests & Resetting Demo Data

```bash
# Backend checks & tests
cd backend
uv run ruff check app tests scripts
uv run mypy app tests scripts
uv run pytest -v

# Frontend checks, tests & PWA build
cd ../frontend
npm run typecheck
npm run test
npm run build

# Reset ONLY simulated demo records (never touches non-simulated data)
# Either click "Reset Demo Data Only" in Admin Demo Controls, or re-run seed_demo.py after clearing simulated rows.
```

---

## Documentation Index
- [Architecture](docs/ARCHITECTURE.md) & [Decision Records (ADRs)](docs/DECISIONS.md)
- [API Specification](docs/API.md) & [Security](docs/SECURITY.md)
- [Live Hackathon Demo & 5-Min Script](docs/DEMO.md)
- [Local & Cloud Deployment Guide](docs/DEPLOYMENT.md)
- [External Services & Offline Fallbacks](docs/EXTERNAL_SERVICES.md)
- [PWA & Offline Behavior](docs/PWA.md)
- [Test Report](docs/TEST_REPORT.md), [Code Audit](docs/CODE_AUDIT.md) & [Known Limitations](docs/KNOWN_LIMITATIONS.md)
