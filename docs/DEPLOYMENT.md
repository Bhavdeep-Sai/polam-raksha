# Deployment Guide — PolamRaksha (పొలంరక్ష)

---

## 1. Primary Deployment: Local Demo Environment

Local Docker Compose is the **primary** hackathon demonstration environment because it keeps PostgreSQL, FastAPI, the background worker, and Vite/PWA running continuously without free-tier sleep interruptions.

### Docker Compose Commands
```bash
cp .env.example .env
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/seed_demo.py --confirm-demo
```

### Resetting Only Simulated Demo Data
Never drop or reset a production database. To clear only `is_simulated=True` demo records:
- Use the Admin UI **Reset Demo Data Only** button (`POST /api/v1/admin/demo/scenario/reset`), which deletes only `is_simulated=True` listings and their linked simulated auctions/orders.

---

## 2. Optional Public Cloud Deployment

If deploying publicly for remote judges:
1. **Static Frontend PWA:** Cloudflare Pages, Netlify, or Vercel (`cd frontend && npm run build`, publish `dist/`). Set `VITE_API_BASE_URL` and `VITE_WS_BASE_URL` to your HTTPS/WSS backend URL.
2. **Backend + Worker:** Render, Railway, or Fly.io (Dockerized `backend/Dockerfile`). Run both the web process (`uvicorn app.main:app`) and the background worker (`python -m app.workers.runner`).
3. **PostgreSQL:** Neon, Supabase, or Railway managed PostgreSQL 16.
4. **Production Security Checklist:**
   - Set `APP_ENV=production`, `DEMO_MODE_ENABLED=false`, `COOKIE_SECURE=true`.
   - Set a strong 32+ char `JWT_SECRET_KEY` and `IVR_WEBHOOK_SECRET`.
   - Restrict `CORS_ORIGINS` to your exact frontend domain.

### Free-Tier Cloud Caveats (Important)
- **Sleeping Containers:** Free web services (e.g., Render Free) sleep after ~15 minutes of inactivity. Cold starts take 30–60s, drop active WebSocket connections, and delay scheduled auction closures.
- **Background Workers:** Many free tiers do not include a persistent background worker process; **do not rely on a sleeping free service for authoritative auction deadlines**.

---

## 3. Estimated Operational Costs (Monthly)

| Tier | Stack | Estimated Cost |
| --- | --- | --- |
| **Local Demo** | Docker Compose on laptop | **\$0 / month** |
| **Low-Cost Pilot** | Cloudflare Pages (Free) + Railway/Fly.io Starter API & Worker + Managed Postgres | **~\$10–\$25 / month** |
| **Production District Scale** | Managed Postgres (HA) + 2x API containers + Worker + Object Storage | **~\$60–\$120 / month** |

