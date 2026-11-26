# External Integrations — PolamRaksha (పొలంరక్ష)

All external integrations sit behind provider interfaces in the backend or progressive UI fallbacks in the frontend. **The core application runs without any external API keys.**

---

## 1. Maps & Tiles (Leaflet + OpenStreetMap)
- **Setup:** Installed via `leaflet` in `frontend/package.json`. Uses standard OpenStreetMap tile URLs (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`) with required `© OpenStreetMap contributors` attribution.
- **Cost & Usage Restrictions:** Free for standard interactive viewing under OpenStreetMap's Tile Usage Policy. **Never bulk-download or pre-scrape public map tiles.**
- **Fallback:** When `navigator.onLine === false` or when toggled by the user, `ProduceMap` switches to an accessible non-map `DataTable` list view.

## 2. Road Routing (OSRM)
- **Setup:** Optional. Set `OSRM_BASE_URL` (e.g., self-hosted OSRM instance or `https://router.project-osrm.org` for light non-production testing) and `OSRM_TIMEOUT_SECONDS` (default `2.5s`).
- **Cost & Usage Restrictions:** Public OSRM demo server has strict rate limits and no SLA; self-hosting OSRM on a regional extract is free (open-source).
- **Fallback:** `resolve_route_with_cache()` checks PostgreSQL `road_distance_cache` first, then tries OSRM with bounded retry (`max_retries=1`), and falls back to `ApproximateHaversineProvider` (`APPROX_STRAIGHT_LINE`), clearly labelled as approximate and not live traffic.

## 3. Agricultural Market Reference Data (CSV/JSON & Data.gov.in)
- **Setup:**
  - **CSV/JSON Import (Zero external dependency):** `POST /api/v1/market-prices/import` for Admin/Operator dataset imports.
  - **Data.gov.in AGMARKNET API (Optional):** Set `DATA_GOV_IN_API_KEY` in `.env` (free registration on data.gov.in).
- **Cost & Usage Restrictions:** Free open government data; subject to Data.gov.in API rate limits.
- **Fallback:** When `DATA_GOV_IN_API_KEY` is unset or unreachable, `OptionalDataGovInProvider.fetch_records()` returns `[]` without failing. Stale observations (> `MARKET_PRICE_STALE_HOURS`, default 48h) are flagged `is_stale=True`.

## 4. Telephony & Speech (Asterisk/SIP, Exotel, Faster Whisper)
- **Setup:**
  - **Browser DTMF Simulator:** Built-in at `/ivr` (zero external dependencies).
  - **Asterisk/SIP & Exotel Webhooks:** Configure `IVR_WEBHOOK_SECRET` for HMAC-SHA256 verification on `/api/v1/ivr/webhooks/{provider}`.
  - **Faster Whisper (Optional):** Install optional `speech` dependency group (`uv sync --extra speech`).
- **Cost & Usage Restrictions:** Real Indian cellular calls via Exotel or telecom trunks require KYC, TRAI DLT approval, and paid telephony credits.
- **Fallback:** If `faster-whisper` is not installed, `transcribe_audio_with_optional_whisper()` returns `available=False` gracefully.

