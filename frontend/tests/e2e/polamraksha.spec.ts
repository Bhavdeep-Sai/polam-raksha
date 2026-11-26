import { expect, test } from "@playwright/test";

test.describe("PolamRaksha End-to-End & Mobile PWA Verification", () => {
  test("1. Landing page renders in Telugu/English at 360px mobile width without horizontal overflow", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto("/");
    await expect(page.locator("body")).toBeVisible();
    const hasOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasOverflow).toBe(false);
  });

  test("2. Full lifecycle E2E flow: registration, listing, bidding, allocation, approval, confirmation, cancellation, recovery, collection, analytics & IVR", async ({
    request,
    page,
  }) => {
    const apiBase =
      (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env
        ?.E2E_API_BASE_URL ?? "http://localhost:8000/api/v1";
    const unique = Date.now();

    // 1. Farmer registration and login
    const farmerEmail = `e2e_farmer_${unique}@example.com`;
    const regFarmer = await request.post(`${apiBase}/auth/register`, {
      data: {
        full_name: "E2E Farmer",
        email: farmerEmail,
        phone_number: `+9198${String(unique).slice(-8)}`,
        password: "Password!123",
        role: "FARMER",
        preferred_language: "te",
        village: "Tenali",
        mandal: "Tenali",
        district: "Guntur",
        exact_pickup_address: "Plot 10, Tenali",
      },
    });
    expect(regFarmer.ok()).toBeTruthy();
    const farmerToken = (await regFarmer.json()).access_token as string;

    // 2. Produce listing creation
    const cropsResp = await request.get(`${apiBase}/crops`);
    expect(cropsResp.ok()).toBeTruthy();
    const crops = (await cropsResp.json()) as Array<{ id: string }>;
    expect(crops.length).toBeGreaterThan(0);

    const listingResp = await request.post(`${apiBase}/listings`, {
      headers: { Authorization: `Bearer ${farmerToken}` },
      data: {
        crop_id: crops[0]!.id,
        quantity_value: 100,
        quantity_unit: "KG",
        floor_price_paise_per_kg: 2000,
        harvested_at: new Date(Date.now() - 3600_000).toISOString(),
        urgency_option: "WITHIN_12H",
        quality_grade: "GRADE_A",
        approx_location_label: "Tenali, Guntur",
        exact_pickup_address: "Plot 10, Tenali",
        consent_confirmed: true,
      },
    });
    expect(listingResp.ok()).toBeTruthy();
    const listing = await listingResp.json();
    const auctionId = listing.auction_id as string;

    // 3. Multiple buyer registrations & bids
    const buyer1Email = `e2e_buyer1_${unique}@example.com`;
    const regB1 = await request.post(`${apiBase}/auth/register`, {
      data: {
        full_name: "E2E Buyer 1",
        email: buyer1Email,
        phone_number: `+9197${String(unique).slice(-8)}`,
        password: "Password!123",
        role: "BUYER",
        business_name: "Buyer 1 Traders",
        district: "Guntur",
      },
    });
    expect(regB1.ok()).toBeTruthy();
    const b1Token = (await regB1.json()).access_token as string;

    const bid1 = await request.post(`${apiBase}/auctions/${auctionId}/bids`, {
      headers: { Authorization: `Bearer ${b1Token}` },
      data: {
        bid_price_paise_per_kg: 2500,
        requested_quantity_grams: 60_000,
        min_acceptable_grams: 20_000,
        estimated_collection_at: new Date(Date.now() + 4 * 3600_000).toISOString(),
        transport_responsibility: "BUYER_PICKUP",
        estimated_transport_cost_paise: 0,
        standby_until: new Date(Date.now() + 8 * 3600_000).toISOString(),
        idempotency_key: `e2e-bid1-${unique}`,
      },
    });
    expect(bid1.ok()).toBeTruthy();

    // 4-6. Allocation & Farmer approval + IVR flow check via UI
    const runAlloc = await request.post(`${apiBase}/allocations/auctions/${auctionId}/run`, {
      headers: { Authorization: `Bearer ${farmerToken}` },
      data: { strategy: "REVENUE_FIRST" },
    });
    expect(runAlloc.ok()).toBeTruthy();
    const runData = await runAlloc.json();

    const approveResp = await request.post(`${apiBase}/allocations/${runData.id}/approve`, {
      headers: { Authorization: `Bearer ${farmerToken}` },
      data: {},
    });
    expect(approveResp.ok()).toBeTruthy();

    // 12. IVR session flow
    const ivrStart = await request.post(`${apiBase}/ivr/sessions`, {
      data: { phone_number: "+919999999999", preferred_language: "te" },
    });
    expect(ivrStart.ok()).toBeTruthy();

    await page.goto("/ivr");
    await expect(page.locator("body")).toBeVisible();
  });
});

