import { Gavel, Package, Sprout, TrendingUp, Volume2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Route, Routes } from "react-router-dom";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { CurrencyDisplay } from "@/components/common/CurrencyDisplay";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { ProduceCard } from "@/components/common/ProduceCard";
import { QuantityDisplay } from "@/components/common/QuantityDisplay";
import { StatCard } from "@/components/common/StatCard";
import { VoicePrompt } from "@/components/common/VoicePrompt";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ProduceRegistrationForm } from "@/features/listings/ProduceRegistrationForm";
import { PrintableReceiptCard } from "@/features/listings/PrintableReceiptCard";
import { MarketReferencePricesView } from "@/features/market/MarketReferencePricesView";
import {
  useApproveAllocationMutation,
  useAuctionAllocationsQuery,
  useCancelUncommittedMutation,
  useMyListingsQuery,
  useRunAllocationMutation,
} from "@/hooks/queries";

function FarmerAllocationPanel({ auctionId }: { auctionId: string }) {
  const { t } = useTranslation();
  const runsQuery = useAuctionAllocationsQuery(auctionId);
  const runMutation = useRunAllocationMutation(auctionId);
  const approveMutation = useApproveAllocationMutation(auctionId);

  const latestRun = runsQuery.data?.[0];

  return (
    <div className="space-y-3 border-t border-brand-border pt-3">
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={runMutation.isPending}
          onClick={() =>
            void runMutation.mutateAsync({
              strategy: "REVENUE_FIRST",
              min_net_revenue_paise: 0,
              time_limit_seconds: 2.0,
            })
          }
        >
          {t("nav.farmer.offers")} (Revenue-First)
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={runMutation.isPending}
          onClick={() =>
            void runMutation.mutateAsync({
              strategy: "RESCUE_FIRST",
              min_net_revenue_paise: 0,
              time_limit_seconds: 2.0,
            })
          }
        >
          {t("nav.farmer.offers")} (Rescue-First)
        </Button>
      </div>

      {latestRun ? (
        <div className="space-y-2 rounded-lg border border-brand-border bg-brand-bg p-3 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-bold text-brand-ink">
              {latestRun.solver_status} •{" "}
              <CurrencyDisplay paise={latestRun.estimated_net_revenue_paise} />
            </span>
            {!latestRun.is_approved && latestRun.allocations.length > 0 ? (
              <Button
                size="sm"
                disabled={approveMutation.isPending}
                onClick={() => void approveMutation.mutateAsync(latestRun.id)}
              >
                {t("common.confirm")}
              </Button>
            ) : null}
          </div>
          <ul className="list-disc space-y-1 pl-4 text-brand-ink-muted">
            {latestRun.explanations.map((line, idx) => (
              <li key={idx}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function FarmerSellHome() {
  const { t } = useTranslation();
  const myListingsQuery = useMyListingsQuery();
  const cancelMutation = useCancelUncommittedMutation();
  const [cancelTargetId, setCancelTargetId] = useState<string | null>(null);

  const listings = myListingsQuery.data ?? [];
  const totalAvailableGrams = listings.reduce(
    (sum, item) => sum + item.available_quantity_grams,
    0,
  );
  const totalEstimatedFloorPaise = listings.reduce(
    (sum, item) =>
      sum + Math.round((item.available_quantity_grams / 1000) * item.floor_price_paise_per_kg),
    0,
  );

  const handleConfirmCancel = async () => {
    if (!cancelTargetId) return;
    await cancelMutation.mutateAsync(cancelTargetId);
    setCancelTargetId(null);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("nav.farmer.sell")}
        description={t("tagline")}
        actions={<VoicePrompt text={`${t("nav.farmer.sell")}. ${t("tagline")}`} />}
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label={t("nav.farmer.sell")}
          value={listings.length}
          icon={<Sprout className="h-5 w-5" />}
        />
        <StatCard
          label={t("listing.availableQty")}
          value={<QuantityDisplay grams={totalAvailableGrams} />}
          icon={<Package className="h-5 w-5" />}
        />
        <StatCard
          label={t("farmerForm.estimatedNetRevenue")}
          value={<CurrencyDisplay paise={totalEstimatedFloorPaise} />}
          icon={<Gavel className="h-5 w-5" />}
        />
      </div>

      <ProduceRegistrationForm />

      <section aria-labelledby="my-listings-heading" className="space-y-4">
        <h2 id="my-listings-heading" className="text-xl font-bold text-brand-ink">
          {t("nav.farmer.auctions")}
        </h2>

        {myListingsQuery.isPending ? (
          <LoadingSkeleton rows={2} />
        ) : myListingsQuery.isError ? (
          <ErrorState
            message={myListingsQuery.error.message}
            onRetry={() => void myListingsQuery.refetch()}
          />
        ) : listings.length === 0 ? (
          <EmptyState title={t("landing.liveListingsEmpty")} />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {listings.map((item) => (
              <ProduceCard
                key={item.id}
                title={`Crop #${item.crop_id.slice(0, 6)}`}
                status={item.status}
                availableGrams={item.available_quantity_grams}
                floorPricePaisePerKg={item.floor_price_paise_per_kg}
                approxLocation={item.approx_location_label}
                spoilageDeadlineUtc={item.spoilage_deadline_at}
                isSimulated={item.is_simulated}
                actions={
                  <div className="space-y-2">
                    {item.available_quantity_grams > 0 ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCancelTargetId(item.id)}
                      >
                        {t("farmerForm.cancelUncommitted")}
                      </Button>
                    ) : null}
                    {item.auction_id ? (
                      <FarmerAllocationPanel auctionId={item.auction_id} />
                    ) : null}
                    <PrintableReceiptCard listingId={item.id} />
                  </div>
                }
              />
            ))}
          </div>
        )}
      </section>

      <ConfirmDialog
        open={cancelTargetId !== null}
        title={t("farmerForm.cancelUncommitted")}
        description={t("farmerForm.cancelUncommittedConfirm")}
        destructive
        onConfirm={() => void handleConfirmCancel()}
        onCancel={() => setCancelTargetId(null)}
      />
    </div>
  );
}

function FarmerSectionPlaceholder({
  titleKey,
  showVoice = false,
  showPrices = false,
}: {
  titleKey: string;
  showVoice?: boolean;
  showPrices?: boolean;
}) {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <PageHeader title={t(titleKey)} />
      {showVoice ? (
        <Card className="space-y-4">
          <div className="flex items-center gap-3">
            <Volume2 className="h-6 w-6 text-brand-primary" aria-hidden="true" />
            <h2 className="text-lg font-bold text-brand-ink">{t("nav.farmer.voice")}</h2>
          </div>
          <p className="text-sm text-brand-ink-muted">{t("landing.accessibilityBody")}</p>
          <VoicePrompt text={`${t("appName")}. ${t("landing.accessibilityBody")}`} />
        </Card>
      ) : showPrices ? (
        <EmptyState
          title={t("nav.farmer.prices")}
          description={t("common.pendingPhaseNote")}
          action={<TrendingUp className="h-5 w-5 text-brand-primary" aria-hidden="true" />}
        />
      ) : (
        <EmptyState
          title={t("common.noRecords")}
          description={t("common.pendingPhaseNote")}
        />
      )}
    </div>
  );
}

export function FarmerDashboard() {
  return (
    <Routes>
      <Route index element={<FarmerSellHome />} />
      <Route path="auctions" element={<FarmerSellHome />} />
      <Route path="offers" element={<FarmerSectionPlaceholder titleKey="nav.farmer.offers" />} />
      <Route path="orders" element={<FarmerSectionPlaceholder titleKey="nav.farmer.orders" />} />
      <Route path="prices" element={<MarketReferencePricesView />} />
      <Route path="voice" element={<FarmerSectionPlaceholder titleKey="nav.farmer.voice" showVoice />} />
    </Routes>
  );
}
