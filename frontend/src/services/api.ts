import { env } from "@/lib/env";
import type { components } from "@/types/api";

export type HealthResponse = components["schemas"]["HealthResponse"];
export type ReadinessResponse = components["schemas"]["ReadinessResponse"];
export type RegisterRequest = components["schemas"]["RegisterRequest"];
export type LoginRequest = components["schemas"]["LoginRequest"];
export type PinLoginRequest = components["schemas"]["PinLoginRequest"];
export type TokenResponse = components["schemas"]["TokenResponse"];
export type UserSummary = components["schemas"]["UserSummary"];
export type LogoutResponse = components["schemas"]["LogoutResponse"];
export type PublicListingResponse = components["schemas"]["PublicListingResponse"];
export type FarmerListingDetailResponse = components["schemas"]["FarmerListingDetailResponse"];
export type CropCatalogItem = components["schemas"]["CropCatalogItem"];
export type SchedulePreviewRequest = components["schemas"]["SchedulePreviewRequest"];
export type SchedulePreviewResponse = components["schemas"]["SchedulePreviewResponse"];
export type CreateListingRequest = components["schemas"]["CreateListingRequest"];
export type UpdateListingRequest = components["schemas"]["UpdateListingRequest"];
export type FarmerPrivateProfileResponse = components["schemas"]["FarmerPrivateProfileResponse"];
export type AssistedFarmerOnboardRequest = components["schemas"]["AssistedFarmerOnboardRequest"];
export type AssistedFarmerSummary = components["schemas"]["AssistedFarmerSummary"];
export type OperatorAssistedOverviewResponse =
  components["schemas"]["OperatorAssistedOverviewResponse"];
export type AuctionDetailResponse = components["schemas"]["AuctionDetailResponse"];
export type BidRevisionPublicResponse = components["schemas"]["BidRevisionPublicResponse"];
export type PlaceBidRequest = components["schemas"]["PlaceBidRequest"];
export type AllocationRunResponse = components["schemas"]["AllocationRunResponse"];
export type RunAllocationRequest = components["schemas"]["RunAllocationRequest"];
export type IvrSessionResponse = components["schemas"]["IvrSessionResponse"];
export type StartIvrSessionRequest = components["schemas"]["StartIvrSessionRequest"];
export type DtmfInputRequest = components["schemas"]["DtmfInputRequest"];
export type ListingReceiptResponse = components["schemas"]["ListingReceiptResponse"];
export type MapPointResponse = components["schemas"]["MapPointResponse"];
export type MarketPriceResponse = components["schemas"]["MarketPriceResponse"];
export type NotificationResponse = components["schemas"]["NotificationResponse"];
export type AdminOperationalOverview = components["schemas"]["AdminOperationalOverview"];
export type AdminUserSummary = components["schemas"]["AdminUserSummary"];
export type OperatorPermissionSummary = components["schemas"]["OperatorPermissionSummary"];
export type DisputeCaseSummary = components["schemas"]["DisputeCaseSummary"];
export type AuditEventSummary = components["schemas"]["AuditEventSummary"];
export type ImpactAnalyticsResponse = components["schemas"]["ImpactAnalyticsResponse"];
export type VerifyBuyerRequest = components["schemas"]["VerifyBuyerRequest"];
export type UpdateUserStatusRequest = components["schemas"]["UpdateUserStatusRequest"];
export type ResolveDisputeRequest = components["schemas"]["ResolveDisputeRequest"];
export interface AuctionEventEnvelope {
  event_id: string;
  event_type: string;
  auction_id: string;
  server_timestamp: string;
  entity_version: number;
  payload: Record<string, unknown>;
}
export type UserRole = UserSummary["role"];

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

const API_V1_BASE = `${env.VITE_API_BASE_URL.replace(/\/$/, "")}/api/v1`;

// Access token is kept strictly in memory (never localStorage).
let inMemoryAccessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token;
}

export function getAccessToken(): string | null {
  return inMemoryAccessToken;
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=")[1] ?? "") : null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };

  if (inMemoryAccessToken) {
    headers.Authorization = `Bearer ${inMemoryAccessToken}`;
  }

  const csrfToken = readCookie("polam_csrf_token");
  if (csrfToken && !headers["X-CSRF-Token"]) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const response = await fetch(`${API_V1_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    let code = "http_error";
    let message = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as {
        error?: { code?: string; message?: string };
      };
      if (body.error?.code) code = body.error.code;
      if (body.error?.message) message = body.error.message;
    } catch {
      // Preserve fallback status message when body is not JSON.
    }
    throw new ApiError(response.status, code, message);
  }

  return (await response.json()) as T;
}

export const apiClient = {
  getHealth: (): Promise<HealthResponse> => request<HealthResponse>("/health"),
  getReadiness: (): Promise<ReadinessResponse> => request<ReadinessResponse>("/ready"),

  register: (payload: RegisterRequest): Promise<UserSummary> =>
    request<UserSummary>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  login: async (payload: LoginRequest): Promise<TokenResponse> => {
    const res = await request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setAccessToken(res.access_token);
    return res;
  },

  pinLogin: async (payload: PinLoginRequest): Promise<TokenResponse> => {
    const res = await request<TokenResponse>("/auth/pin-login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setAccessToken(res.access_token);
    return res;
  },

  refresh: async (): Promise<TokenResponse> => {
    const res = await request<TokenResponse>("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({}),
    });
    setAccessToken(res.access_token);
    return res;
  },

  logout: async (): Promise<LogoutResponse> => {
    try {
      return await request<LogoutResponse>("/auth/logout", {
        method: "POST",
        body: JSON.stringify({}),
      });
    } finally {
      setAccessToken(null);
    }
  },

  getMe: (): Promise<UserSummary> => request<UserSummary>("/auth/me"),

  getCrops: (): Promise<CropCatalogItem[]> => request<CropCatalogItem[]>("/crops"),

  getPublicListings: (): Promise<PublicListingResponse[]> =>
    request<PublicListingResponse[]>("/listings"),

  getMyListings: (farmerId?: string): Promise<FarmerListingDetailResponse[]> =>
    request<FarmerListingDetailResponse[]>(
      farmerId ? `/listings/mine?farmer_id=${encodeURIComponent(farmerId)}` : "/listings/mine",
    ),

  previewListingSchedule: (
    payload: SchedulePreviewRequest,
  ): Promise<SchedulePreviewResponse> =>
    request<SchedulePreviewResponse>("/listings/schedule-preview", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  createListing: (payload: CreateListingRequest): Promise<FarmerListingDetailResponse> =>
    request<FarmerListingDetailResponse>("/listings", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateListing: (
    listingId: string,
    payload: UpdateListingRequest,
  ): Promise<FarmerListingDetailResponse> =>
    request<FarmerListingDetailResponse>(`/listings/${listingId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  cancelUncommittedListing: (listingId: string): Promise<FarmerListingDetailResponse> =>
    request<FarmerListingDetailResponse>(`/listings/${listingId}/cancel-uncommitted`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  getFarmerPrivateProfile: (farmerId: string): Promise<FarmerPrivateProfileResponse> =>
    request<FarmerPrivateProfileResponse>(`/farmers/${farmerId}/profile`),

  getAssistedOverview: (): Promise<OperatorAssistedOverviewResponse> =>
    request<OperatorAssistedOverviewResponse>("/farmers/assisted"),

  onboardFarmerAssisted: (
    payload: AssistedFarmerOnboardRequest,
  ): Promise<AssistedFarmerSummary> =>
    request<AssistedFarmerSummary>("/farmers/assisted", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getOpenAuctions: (): Promise<AuctionDetailResponse[]> =>
    request<AuctionDetailResponse[]>("/auctions"),

  getAuctionDetail: (auctionId: string): Promise<AuctionDetailResponse> =>
    request<AuctionDetailResponse>(`/auctions/${auctionId}`),

  placeBid: (
    auctionId: string,
    payload: PlaceBidRequest,
  ): Promise<AuctionDetailResponse> =>
    request<AuctionDetailResponse>(`/auctions/${auctionId}/bids`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  runAllocation: (
    auctionId: string,
    payload: RunAllocationRequest,
  ): Promise<AllocationRunResponse> =>
    request<AllocationRunResponse>(`/allocations/auctions/${auctionId}/run`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getAuctionAllocations: (auctionId: string): Promise<AllocationRunResponse[]> =>
    request<AllocationRunResponse[]>(`/allocations/auctions/${auctionId}`),

  approveAllocation: (runId: string): Promise<AllocationRunResponse> =>
    request<AllocationRunResponse>(`/allocations/${runId}/approve`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  getAdminAllocationRuns: (): Promise<AllocationRunResponse[]> =>
    request<AllocationRunResponse[]>("/allocations/runs"),

  getListingReceipt: (listingId: string): Promise<ListingReceiptResponse> =>
    request<ListingReceiptResponse>(`/listings/${listingId}/receipt`),

  startIvrSession: (payload: StartIvrSessionRequest): Promise<IvrSessionResponse> =>
    request<IvrSessionResponse>("/ivr/sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  sendIvrDtmf: (
    sessionId: string,
    payload: DtmfInputRequest,
  ): Promise<IvrSessionResponse> =>
    request<IvrSessionResponse>(`/ivr/sessions/${sessionId}/dtmf`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getMapPoints: (): Promise<MapPointResponse[]> =>
    request<MapPointResponse[]>("/logistics/map-points"),

  getMarketPrices: (): Promise<MarketPriceResponse[]> =>
    request<MarketPriceResponse[]>("/market-prices"),

  getMyNotifications: (): Promise<NotificationResponse[]> =>
    request<NotificationResponse[]>("/notifications"),

  acknowledgeNotification: (notificationId: string): Promise<NotificationResponse> =>
    request<NotificationResponse>(`/notifications/${notificationId}/acknowledge`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  getAdminOverview: (): Promise<AdminOperationalOverview> =>
    request<AdminOperationalOverview>("/admin/overview"),

  getAdminUsers: (role?: string): Promise<AdminUserSummary[]> =>
    request<AdminUserSummary[]>(role ? `/admin/users?role=${encodeURIComponent(role)}` : "/admin/users"),

  updateAdminUserStatus: (
    userId: string,
    payload: UpdateUserStatusRequest,
  ): Promise<AdminUserSummary> =>
    request<AdminUserSummary>(`/admin/users/${userId}/status`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  verifyBuyer: (buyerId: string, payload: VerifyBuyerRequest): Promise<AdminUserSummary> =>
    request<AdminUserSummary>(`/admin/buyers/${buyerId}/verify`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getOperatorPermissions: (): Promise<OperatorPermissionSummary[]> =>
    request<OperatorPermissionSummary[]>("/admin/operator-permissions"),

  revokeOperatorPermission: (relationshipId: string): Promise<OperatorPermissionSummary> =>
    request<OperatorPermissionSummary>(`/admin/operator-permissions/${relationshipId}/revoke`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  getAdminDisputes: (): Promise<DisputeCaseSummary[]> =>
    request<DisputeCaseSummary[]>("/admin/disputes"),

  resolveAdminDispute: (
    disputeId: string,
    payload: ResolveDisputeRequest,
  ): Promise<DisputeCaseSummary> =>
    request<DisputeCaseSummary>(`/admin/disputes/${disputeId}/resolve`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getAdminAuditEvents: (action?: string): Promise<AuditEventSummary[]> =>
    request<AuditEventSummary[]>(
      action ? `/admin/audit-events?action=${encodeURIComponent(action)}` : "/admin/audit-events",
    ),

  getImpactAnalytics: (params: {
    start_date?: string;
    end_date?: string;
    crop_code?: string;
    location?: string;
    include_simulated?: boolean;
  }): Promise<ImpactAnalyticsResponse> => {
    const search = new URLSearchParams();
    if (params.start_date) search.set("start_date", params.start_date);
    if (params.end_date) search.set("end_date", params.end_date);
    if (params.crop_code) search.set("crop_code", params.crop_code);
    if (params.location) search.set("location", params.location);
    if (params.include_simulated) search.set("include_simulated", "true");
    const qs = search.toString();
    return request<ImpactAnalyticsResponse>(`/analytics/impact${qs ? `?${qs}` : ""}`);
  },

  getDemoStatus: (): Promise<{
    demo_mode_enabled: boolean;
    app_env: string;
    demo_auction_duration_seconds: number;
  }> => request("/admin/demo/status"),

  startDemoScenario: (): Promise<{
    listing_id: string;
    auction_id: string;
    quantity_grams: number;
    ends_at: string;
  }> =>
    request("/admin/demo/scenario/start", {
      method: "POST",
      body: JSON.stringify({}),
    }),

  simulateDemoBids: (auctionId: string): Promise<{ auction_id: string; bids_placed: number }> =>
    request("/admin/demo/scenario/simulate-bids", {
      method: "POST",
      body: JSON.stringify({ auction_id: auctionId }),
    }),

  advanceDemoAllocate: (
    auctionId: string,
  ): Promise<{
    auction_id: string;
    allocation_run_id: string;
    solver_status: string;
    orders_created: number;
  }> =>
    request("/admin/demo/scenario/advance-allocate", {
      method: "POST",
      body: JSON.stringify({ auction_id: auctionId }),
    }),

  simulateDemoCancellation: (
    auctionId: string,
  ): Promise<{
    cancelled_order_id: string;
    released_grams: number;
    recovered_orders: number;
  }> =>
    request("/admin/demo/scenario/simulate-cancellation", {
      method: "POST",
      body: JSON.stringify({ auction_id: auctionId }),
    }),

  recordDemoCollection: (
    auctionId: string,
  ): Promise<{ listing_id: string; collected_grams: number }> =>
    request("/admin/demo/scenario/record-collection", {
      method: "POST",
      body: JSON.stringify({ auction_id: auctionId }),
    }),

  resetDemoScenario: (): Promise<{ cleared_simulated_listings: number }> =>
    request("/admin/demo/scenario/reset", {
      method: "POST",
      body: JSON.stringify({}),
    }),
};
