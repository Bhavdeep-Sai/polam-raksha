import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  apiClient,
  type AssistedFarmerOnboardRequest,
  type CreateListingRequest,
  type PlaceBidRequest,
  type RegisterRequest,
  type ResolveDisputeRequest,
  type RunAllocationRequest,
  type SchedulePreviewRequest,
  type UpdateUserStatusRequest,
  type VerifyBuyerRequest,
} from "@/services/api";

export const queryKeys = {
  system: {
    health: ["system", "health"] as const,
    ready: ["system", "ready"] as const,
  },
  crops: {
    all: ["crops", "all"] as const,
  },
  listings: {
    public: ["listings", "public"] as const,
    mine: (farmerId?: string) => ["listings", "mine", farmerId ?? "self"] as const,
  },
  auctions: {
    open: ["auctions", "open"] as const,
    detail: (auctionId: string) => ["auctions", "detail", auctionId] as const,
  },
  allocations: {
    byAuction: (auctionId: string) => ["allocations", "auction", auctionId] as const,
    adminAll: ["allocations", "admin"] as const,
  },
  logistics: {
    mapPoints: ["logistics", "mapPoints"] as const,
  },
  marketPrices: {
    all: ["marketPrices", "all"] as const,
  },
  notifications: {
    mine: ["notifications", "mine"] as const,
  },
  admin: {
    overview: ["admin", "overview"] as const,
    users: (role?: string) => ["admin", "users", role ?? "all"] as const,
    permissions: ["admin", "permissions"] as const,
    disputes: ["admin", "disputes"] as const,
    audit: (action?: string) => ["admin", "audit", action ?? "all"] as const,
  },
  analytics: {
    impact: (params: Record<string, unknown>) => ["analytics", "impact", params] as const,
  },
  farmers: {
    profile: (farmerId: string) => ["farmers", "profile", farmerId] as const,
    assisted: ["farmers", "assisted"] as const,
  },
};

export function useHealthQuery() {
  return useQuery({
    queryKey: queryKeys.system.health,
    queryFn: apiClient.getHealth,
  });
}

export function useReadinessQuery() {
  return useQuery({
    queryKey: queryKeys.system.ready,
    queryFn: apiClient.getReadiness,
  });
}

export function useCropsQuery() {
  return useQuery({
    queryKey: queryKeys.crops.all,
    queryFn: apiClient.getCrops,
  });
}

export function usePublicListingsQuery() {
  return useQuery({
    queryKey: queryKeys.listings.public,
    queryFn: apiClient.getPublicListings,
  });
}

export function useMyListingsQuery(farmerId?: string) {
  return useQuery({
    queryKey: queryKeys.listings.mine(farmerId),
    queryFn: () => apiClient.getMyListings(farmerId),
  });
}

export function useAssistedOverviewQuery() {
  return useQuery({
    queryKey: queryKeys.farmers.assisted,
    queryFn: apiClient.getAssistedOverview,
  });
}

export function useRegisterMutation() {
  return useMutation({
    mutationFn: (payload: RegisterRequest) => apiClient.register(payload),
  });
}

export function useSchedulePreviewMutation() {
  return useMutation({
    mutationFn: (payload: SchedulePreviewRequest) =>
      apiClient.previewListingSchedule(payload),
  });
}

export function useCreateListingMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateListingRequest) => apiClient.createListing(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.listings.public });
      void queryClient.invalidateQueries({ queryKey: ["listings", "mine"] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.farmers.assisted });
    },
  });
}

export function useCancelUncommittedMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (listingId: string) => apiClient.cancelUncommittedListing(listingId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.listings.public });
      void queryClient.invalidateQueries({ queryKey: ["listings", "mine"] });
    },
  });
}

export function useAssistedOnboardMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AssistedFarmerOnboardRequest) =>
      apiClient.onboardFarmerAssisted(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.farmers.assisted });
    },
  });
}

export function useOpenAuctionsQuery() {
  return useQuery({
    queryKey: queryKeys.auctions.open,
    queryFn: apiClient.getOpenAuctions,
  });
}

export function useAuctionDetailQuery(auctionId: string) {
  return useQuery({
    queryKey: queryKeys.auctions.detail(auctionId),
    queryFn: () => apiClient.getAuctionDetail(auctionId),
    enabled: Boolean(auctionId),
  });
}

export function usePlaceBidMutation(auctionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PlaceBidRequest) => apiClient.placeBid(auctionId, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.auctions.detail(auctionId), updated);
      void queryClient.invalidateQueries({ queryKey: queryKeys.auctions.open });
    },
  });
}

export function useAuctionAllocationsQuery(auctionId: string | null) {
  return useQuery({
    queryKey: queryKeys.allocations.byAuction(auctionId ?? ""),
    queryFn: () => apiClient.getAuctionAllocations(auctionId ?? ""),
    enabled: Boolean(auctionId),
  });
}

export function useAdminAllocationRunsQuery() {
  return useQuery({
    queryKey: queryKeys.allocations.adminAll,
    queryFn: apiClient.getAdminAllocationRuns,
  });
}

export function useRunAllocationMutation(auctionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RunAllocationRequest) =>
      apiClient.runAllocation(auctionId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.allocations.byAuction(auctionId),
      });
    },
  });
}

export function useApproveAllocationMutation(auctionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => apiClient.approveAllocation(runId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.allocations.byAuction(auctionId),
      });
      void queryClient.invalidateQueries({ queryKey: ["listings", "mine"] });
    },
  });
}

export function useMapPointsQuery() {
  return useQuery({
    queryKey: queryKeys.logistics.mapPoints,
    queryFn: apiClient.getMapPoints,
  });
}

export function useMarketPricesQuery() {
  return useQuery({
    queryKey: queryKeys.marketPrices.all,
    queryFn: apiClient.getMarketPrices,
  });
}

export function useMyNotificationsQuery() {
  return useQuery({
    queryKey: queryKeys.notifications.mine,
    queryFn: apiClient.getMyNotifications,
  });
}

export function useAcknowledgeNotificationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.acknowledgeNotification(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.notifications.mine });
    },
  });
}

export function useAdminOverviewQuery() {
  return useQuery({
    queryKey: queryKeys.admin.overview,
    queryFn: apiClient.getAdminOverview,
  });
}

export function useAdminUsersQuery(role?: string) {
  return useQuery({
    queryKey: queryKeys.admin.users(role),
    queryFn: () => apiClient.getAdminUsers(role),
  });
}

export function useUpdateAdminUserStatusMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, payload }: { userId: string; payload: UpdateUserStatusRequest }) =>
      apiClient.updateAdminUserStatus(userId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "audit"] });
    },
  });
}

export function useVerifyBuyerMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ buyerId, payload }: { buyerId: string; payload: VerifyBuyerRequest }) =>
      apiClient.verifyBuyer(buyerId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "audit"] });
    },
  });
}

export function useOperatorPermissionsQuery() {
  return useQuery({
    queryKey: queryKeys.admin.permissions,
    queryFn: apiClient.getOperatorPermissions,
  });
}

export function useRevokeOperatorPermissionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (relationshipId: string) => apiClient.revokeOperatorPermission(relationshipId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.admin.permissions });
      void queryClient.invalidateQueries({ queryKey: ["admin", "audit"] });
    },
  });
}

export function useAdminDisputesQuery() {
  return useQuery({
    queryKey: queryKeys.admin.disputes,
    queryFn: apiClient.getAdminDisputes,
  });
}

export function useResolveDisputeMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ disputeId, payload }: { disputeId: string; payload: ResolveDisputeRequest }) =>
      apiClient.resolveAdminDispute(disputeId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.admin.disputes });
      void queryClient.invalidateQueries({ queryKey: queryKeys.admin.overview });
      void queryClient.invalidateQueries({ queryKey: ["admin", "audit"] });
    },
  });
}

export function useAdminAuditEventsQuery(action?: string) {
  return useQuery({
    queryKey: queryKeys.admin.audit(action),
    queryFn: () => apiClient.getAdminAuditEvents(action),
  });
}

export function useImpactAnalyticsQuery(params: {
  start_date?: string;
  end_date?: string;
  crop_code?: string;
  location?: string;
  include_simulated?: boolean;
}) {
  return useQuery({
    queryKey: queryKeys.analytics.impact(params),
    queryFn: () => apiClient.getImpactAnalytics(params),
  });
}
