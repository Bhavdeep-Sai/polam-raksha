import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import "@/lib/i18n";
import App from "@/app/App";
import { ProduceRegistrationForm } from "@/features/listings/ProduceRegistrationForm";
import { formatCurrencyPaise, formatQuantityGrams } from "@/lib/format";
import { apiClient } from "@/services/api";

describe("PolamRaksha Frontend", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.history.pushState({}, "", "/");
    vi.spyOn(apiClient, "refresh").mockRejectedValue(new Error("no session"));
    vi.spyOn(apiClient, "getPublicListings").mockResolvedValue([
      {
        id: "11111111-1111-1111-1111-111111111111",
        crop_id: "22222222-2222-2222-2222-222222222222",
        status: "ACTIVE",
        available_quantity_grams: 120_000,
        floor_price_paise_per_kg: 2450,
        harvested_at: "2026-11-26T04:00:00Z",
        spoilage_deadline_at: "2026-11-28T04:00:00Z",
        approx_location_label: "Tadikonda Mandal, Guntur",
        approx_latitude: 16.42,
        approx_longitude: 80.45,
        quality_grade: "GRADE_A",
        transport_responsibility: "BUYER_PICKUP",
        urgency_option: "WITHIN_24H",
        is_direct_offer_mode: false,
        is_simulated: true,
      },
    ]);
  });

  it("renders landing page and switches between Telugu and English", async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("Tadikonda Mandal, Guntur")).toBeInTheDocument();
    });

    const toggleButton = screen.getByRole("button", { name: /భాష|Language/i });
    fireEvent.click(toggleButton);

    await waitFor(() => {
      expect(
        screen.getByText("Rescue Unsold Perishable Harvests Before Spoilage"),
      ).toBeInTheDocument();
    });
  });

  it("renders system connectivity route with live health and readiness", async () => {
    window.history.pushState({}, "", "/system");
    vi.spyOn(apiClient, "getHealth").mockResolvedValue({
      status: "ok",
      service: "PolamRaksha",
      environment: "test",
      timestamp_utc: "2026-11-26T06:00:00Z",
    });
    vi.spyOn(apiClient, "getReadiness").mockResolvedValue({
      status: "ready",
      database: "connected",
      timestamp_utc: "2026-11-26T06:00:00Z",
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/^(కనెక్ట్ అయింది|Connected)$/)).toBeInTheDocument();
      expect(screen.getByText(/^(సిద్ధంగా ఉంది|Ready)$/)).toBeInTheDocument();
    });
  });

  it("redirects unauthenticated users from protected role dashboards to login", async () => {
    window.history.pushState({}, "", "/farmer");
    render(<App />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { level: 1, name: /లాగిన్|Sign In/i }),
      ).toBeInTheDocument();
    });
  });

  it("formats paise currency and gram quantities consistently", () => {
    expect(formatCurrencyPaise(2450, "en-IN")).toContain("24.50");
    expect(formatQuantityGrams(500, "en")).toBe("500 g");
    expect(formatQuantityGrams(120_000, "en")).toBe("120 kg");
    expect(formatQuantityGrams(120_000, "te")).toBe("120 కిలో");
  });

  it("renders Telugu-first produce registration form with crop catalog and gram conversion", async () => {
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

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={qc}>
        <ProduceRegistrationForm />
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("టమాటా")).toBeInTheDocument();
    });
    expect(screen.getByText(/50000/)).toBeInTheDocument();
  });
});
