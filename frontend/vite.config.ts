import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "prompt",
      includeAssets: ["icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-512.png", "icons/apple-touch-icon.png"],
      manifest: {
        name: "PolamRaksha (పొలంరక్ష) — Save the Harvest",
        short_name: "PolamRaksha",
        description:
          "Agricultural surplus recovery platform for farmers, buyers, and operators.",
        theme_color: "#205438",
        background_color: "#F7F6EE",
        display: "standalone",
        start_url: "/",
        scope: "/",
        lang: "te",
        icons: [
          {
            src: "/icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "/icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
          },
          {
            src: "/icons/icon-maskable-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff,woff2}"],
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/ws\//],
        runtimeCaching: [
          {
            // Explicitly permitted public reference data only
            urlPattern: ({ url }) =>
              /^\/api\/v1\/(crops|market-prices)$/.test(url.pathname),
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "polam-public-reference",
              expiration: {
                maxEntries: 30,
                maxAgeSeconds: 60 * 60,
              },
            },
          },
          {
            // Never cache auth, private orders, farmer PII, or live auction state
            urlPattern: ({ url }) => url.pathname.startsWith("/api/"),
            handler: "NetworkOnly",
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    globals: true,
    exclude: ["tests/e2e/**", "node_modules/**"],
  },
});
