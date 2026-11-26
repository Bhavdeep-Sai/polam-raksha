import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import "@/lib/i18n";
import { PwaStatusBar } from "@/components/common/PwaStatusBar";
import { LiveAuctionView } from "@/features/auctions/LiveAuctionView";
import { ProduceRegistrationForm } from "@/features/listings/ProduceRegistrationForm";
import { apiClient } from "@/services/api";

describe("PolamRaksha PWA & Offline Acceptance Tests", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      get: () => true,
    });
  });

  it("displays offline status, retry controls, and refreshes queries upon reconnection", async () => {
    let online = false;
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      get: () => online,
    });

    const qc = new QueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");

    render(
      <QueryClientProvider client={qc}>
        <PwaStatusBar />
      </QueryClientProvider>,
    );

    expect(screen.getByText(/Offline Mode/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Retry Sync/i })).toBeInTheDocument();

    online = true;
    fireEvent(window, new Event("online"));

    await waitFor(() => {
      expect(screen.getByText(/Online · Last synced:/i)).toBeInTheDocument();
      expect(invalidateSpy).toHaveBeenCalled();
    });
  });

  it("saves and retains offline listing drafts locally and marks them unpublished", async () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      get: () => false,
    });

    vi.spyOn(apiClient, "getCrops").mockResolvedValue([
      {
        id: "33333333-3333-3333-3333-333333333333",
        code: "TOMATO",
        name_en: "Tomato",
        name_te: "టమాటా",
        unit_label_en: "kg",
        unit_label_te: "కిలో",
        default_shelf_life_hours: 48,
      },
    ]);

    const qc = new QueryClient();
    const { unmount } = render(
      <QueryClientProvider client={qc}>
        <ProduceRegistrationForm />
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Save Local Draft/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Save Local Draft/i }));

    expect(
      screen.getByText(/Local Offline Draft Saved — This draft is NOT a published listing/i),
    ).toBeInTheDocument();
    expect(localStorage.getItem("polam_offline_listing_draft_v1")).not.toBeNull();

    // Unmount and remount to confirm retention
    unmount();
    render(
      <QueryClientProvider client={qc}>
        <ProduceRegistrationForm />
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Local Offline Draft Saved — This draft is NOT a published listing/i),
      ).toBeInTheDocument();
    });
  });

  it("prevents silent offline bid submission on live auctions", async () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      get: () => false,
    });

    vi.spyOn(apiClient, "getAuctionDetail").mockResolvedValue({
      id: "44444444-4444-4444-4444-444444444444",
      listing_id: "11111111-1111-1111-1111-111111111111",
      status: "OPEN",
      min_bid_paise_per_kg: 2000,
      min_increment_paise_per_kg: 50,
      starts_at: "2026-11-26T04:00:00Z",
      ends_at: "2026-11-26T12:00:00Z",
      hard_close_at: "2026-11-26T12:30:00Z",
      soft_close_trigger_seconds: 120,
      soft_close_extension_seconds: 120,
      soft_close_max_extension_seconds: 600,
      soft_close_extended_seconds: 0,
      is_direct_offer_mode: false,
      soft_closed_triggered: false,
      version: 1,
      available_quantity_grams: 100_000,
      spoilage_deadline_at: "2026-11-27T04:00:00Z",
      approx_location_label: "Tenali, Guntur",
      highest_unit_price_paise_per_kg: null,
      server_time_utc: "2026-11-26T06:00:00Z",
      active_offers: [],
      my_bid_revisions: [],
    });

    const qc = new QueryClient();
    render(
      <QueryClientProvider client={qc}>
        <LiveAuctionView auctionId="44444444-4444-4444-4444-444444444444" />
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Offline — Live auction bids cannot be queued or submitted/i),
      ).toBeInTheDocument();
    });
  });
});
