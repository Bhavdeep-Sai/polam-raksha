# External Services & Offline Fallback Matrix — PolamRaksha

PolamRaksha is designed so **100% of core workflows work with zero external API keys or internet access**. Every external integration sits behind a provider interface with a local fallback.

| Integration | Env Variable | When Configured | When Disabled / Offline (Default) |
| --- | --- | --- | --- |
| **OSRM Road Routing** | `OSRM_BASE_URL` | Queries OSRM `/route/v1/driving` with timeout (`2.5s`) and bounded retry; caches in `road_distance_cache`. | Uses `road_distance_cache` first, then `ApproximateHaversineProvider` clearly labelled `APPROX_STRAIGHT_LINE` (no live traffic claims). |
| **data.gov.in Market Prices** | `DATA_GOV_IN_API_KEY` | Fetches mandi rates via adapter and normalizes `QUINTAL` to `paise/kg`. | Uses local CSV/JSON import (`POST /api/v1/market-prices/import`) and seeded simulated sample rates (`is_simulated=True`). |
| **OpenStreetMap Map Tiles** | None (public tiles) | Renders interactive Leaflet map with OSM attribution. | Falls back cleanly to a structured non-map produce list view (`ProduceMap.tsx`). |
| **Telephony / SMS / Voice** | `IVR_WEBHOOK_SECRET` | Verifies HMAC webhook signatures and dispatches via `TelephonyNotificationProvider`. | Uses browser IVR simulator (`/ivr`), local Telugu `.wav` cues + `speechSynthesis`, and marks `telephone` notifications `FAILED` rather than falsely claiming SMS delivery. |
| **Speech Recognition** | Optional `SpeechRecognition` | Parses spoken transcript via `voice_adapter.py`. | Deterministic rule-based Telugu/English keyword & quantity extraction (`extract_listing_fields_from_transcript`). |

