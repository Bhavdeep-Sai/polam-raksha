# PolamRaksha Progressive Web Application (PWA) Architecture & Limitations

## 1. Overview
PolamRaksha's existing React + Vite + TypeScript frontend (`frontend/`) is configured as an installable Progressive Web Application using `vite-plugin-pwa` and Workbox (`frontend/vite.config.ts`). There is **no second frontend codebase**.

- **Web App Manifest:** Generated at build time (`manifest.webmanifest`) with `display: "standalone"`, `theme_color: "#205438"`, `background_color: "#F7F6EE"`, `lang: "te"`, and 192x192, 512x512, and 512x512 maskable icons in `frontend/public/icons/`.
- **Service Worker Update Handling:** Uses `registerType: "prompt"` with `virtual:pwa-register` in `PwaStatusBar.tsx` so users see an explicit **"Update Available — Reload"** button when a new build is ready.

---

## 2. Offline Caching & Security Boundaries

| Resource Category | Caching Strategy | Rationale |
| --- | --- | --- |
| Static UI shell, JS/CSS, self-hosted Inter & Noto Sans Telugu fonts, icons | **Precache** (`globPatterns`) + `navigateFallback: "/index.html"` | Enables instant app shell startup on flaky rural networks (`360px`+ responsive layouts). |
| Public reference data (`GET /api/v1/crops`, `GET /api/v1/market-prices`) | **StaleWhileRevalidate** (`polam-public-reference`, 1h TTL) | Safe non-PII agricultural catalog and reference rates. |
| Auth, farmer PII, private orders, live auctions, allocations, admin (`/api/*`, `/ws/*`) | **NetworkOnly** (`navigateFallbackDenylist` + Workbox route rule) | Never caches JWTs, farmer addresses, private orders, or stale auction prices. |

---

## 3. Offline Farmer Drafts & Live Action Guards

- **Local Offline Drafts (`ProduceRegistrationForm.tsx`):** Farmers can save produce listing drafts locally in `localStorage` (`polam_offline_listing_draft_v1`). A prominent banner states that local drafts are **not published listings** until connected and confirmed online.
- **No Silent Offline Bid Queuing (`LiveAuctionView.tsx`):** Time-sensitive auction bids, offer approvals, and order commitments are **disabled offline** and require live online validation.
- **Reconnection Refresh (`useNetworkStatus.ts`):** When `window` receives an `online` event, all active TanStack Query caches are invalidated to refresh authoritative auction and listing state.

---

## 4. Platform-Specific Limitations (Android vs. iOS)

| Capability | Android (Chrome / Edge / Samsung Internet) | iOS / iPadOS (Safari WebKit) |
| --- | --- | --- |
| **Install Prompt** | Supports `beforeinstallprompt` event; PolamRaksha displays an **"Install App"** button in `PwaStatusBar`. | Does **not** support `beforeinstallprompt`. Users must tap **Share → Add to Home Screen** (guidance shown automatically on iOS Safari). |
| **Background WebSockets & Sync** | WebSockets stay active longer in foreground; Background Sync API supported (intentionally unused for time-sensitive bids). | Safari aggressively suspends WebSockets and service workers when backgrounded; reconnection automatically refreshes state when resumed. |
| **Offline Storage Eviction** | Persistent storage quota is generous for installed PWAs. | Safari may evict `localStorage` / Cache Storage after ~7 days of inactivity if not added to the Home Screen. |
| **Web Notifications** | Supported via Notification API when granted. | Supported only for Home Screen-installed PWAs on iOS 16.4+. |

