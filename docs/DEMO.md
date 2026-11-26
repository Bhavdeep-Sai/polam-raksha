# Live Hackathon Demo Guide — PolamRaksha (పొలంరక్ష)

---

## 1. Pre-Demo Checklist (Offline-Ready)

1. Ensure `.env` has `APP_ENV=development`, `DEMO_MODE_ENABLED=true`, `DEMO_AUCTION_DURATION_SECONDS=120`.
2. Start services (`docker compose up --build -d` or native backend + worker + frontend).
3. Run migrations and seed simulated demo data:
   ```bash
   cd backend
   uv run alembic upgrade head
   uv run python scripts/seed_demo.py --confirm-demo
   ```
4. Verify `http://localhost:8000/api/v1/ready` returns `{"status": "ready", "database": "connected"}`.
5. Open `http://localhost:5173` — Telugu (`తెలుగు`) / English toggle, cached route matrix, simulated mandi prices, and local Telugu audio cues work **with zero external API keys or internet access**.

---

## 2. Five-Minute Hackathon Presentation Script

1. **0:00–0:45 | Problem & Bilingual Accessibility:**
   - Open `http://localhost:5173` (360px mobile view + Telugu UI). Explain how 30%+ of perishable harvests spoil due to fragmented mandi discovery and last-minute buyer cancellations.
   - Show that PolamRaksha serves smartphone PWA users, keypad phone farmers (via `/ivr`), and zero-phone farmers (via Operator assisted access).
2. **0:45–1:45 | Telugu Keypad IVR Registration (300 kg Tomatoes):**
   - Navigate to `/ivr`, dial `demo.farmer1` (`+919000000001`, PIN `1234`), and register 300 kg of Tomatoes with reserve price and urgency. Show how it calls the **same** backend listing/auction service as the web app.
3. **1:45–3:00 | Live Competitive Auction & OR-Tools CP-SAT Allocation:**
   - Log in as Admin (`demo.admin@polamraksha.local` / `DemoAdmin#2026`) -> **Admin Demo Controls** (clearly marked `DEMO DATA`).
   - Click **1. Start 300 kg Scenario** -> **2. Simulate Bids (3+ Buyers)** (shows 3 buyers + competitive bid increase).
   - Click **3. Close & Allocate (CP-SAT)** -> show deterministic optimal multi-buyer allocation with integer-paise/gram math and human-readable explanations.
4. **3:00–4:15 | Cancellation Recovery & Collection:**
   - Click **4. Cancel 1 Order & Recover** -> demonstrate that **only** the cancelled quantity is released back to `available_quantity_grams` and re-allocated to the standby buyer.
   - Click **5. Record Collection** -> open **Analytics** (`Show Simulated Demo Separately`) to show real-time Recharts updates separating `Allocated`, `Collected`, `Cancelled`, `Recovered`, and `Demo` vs `Production` data.
5. **4:15–5:00 | Offline PWA Resilience & Close:**
   - Toggle browser DevTools to **Offline**: show cached shell, local unpublished draft saving, and live bid blocking (no silent stale bid queuing).

---

## 3. Optimization Algorithm Explanation (CP-SAT)

PolamRaksha models produce allocation as a constrained integer optimization problem solved by **Google OR-Tools CP-SAT** (`backend/app/modules/allocation/solver.py`):
- **Units:** Integer **grams** (1 kg granularity) and integer **paise** (no floating-point drift).
- **Hard Constraints:** Total allocated <= `available_quantity_grams`; buyer MOQ/MaxQ respected; offer price >= reserve price; estimated collection <= hard spoilage deadline; excluded/cancelled buyers ignored; fixed pickup cost charged at most once per selected buyer.
- **Lexicographic Strategies:** `REVENUE_FIRST` maximizes net farmer revenue (`gross - farmer_paid_transport`) then allocated quantity; `RESCUE_FIRST` maximizes rescued quantity within a revenue floor, then net revenue.
- **Fallback:** If CP-SAT exceeds its time limit, a deterministic greedy fallback runs and records `used_fallback = True`.

---

## 4. Judge Q&A Preparation

- **Q: Why a modular monolith instead of microservices?**  
  *A: Auctions, inventory reservation, and cancellation recovery require strict ACID transactions (`SELECT ... FOR UPDATE`) and database `CheckConstraint`s so two buyers never oversell the same crate of tomatoes.*
- **Q: What happens if a farmer has no smartphone or internet?**  
  *A: They can call the Telugu keypad IVR state machine (`*`/`#`/DTMF) or visit a local Operator who registers on their behalf with recorded consent and a printable receipt.*
- **Q: Can demo mode leak into production?**  
  *A: No. `Settings.reject_demo_mode_in_production` raises a startup error if `APP_ENV=production` and `DEMO_MODE_ENABLED=true`, and all demo endpoints reject non-admin or production requests with HTTP `403`.*
