import { Gavel, Shield, TrendingUp } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Route, Routes } from "react-router-dom";

import { AuctionStatus } from "@/components/common/AuctionStatus";
import { CurrencyDisplay } from "@/components/common/CurrencyDisplay";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { QuantityDisplay } from "@/components/common/QuantityDisplay";
import { StatCard } from "@/components/common/StatCard";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { LiveAuctionView } from "@/features/auctions/LiveAuctionView";
import { ProduceMap } from "@/features/logistics/ProduceMap";
import { useOpenAuctionsQuery } from "@/hooks/queries";

function BuyerDiscoveryHome() {
  const { t } = useTranslation();
  const auctionsQuery = useOpenAuctionsQuery();
  const [selectedAuctionId, setSelectedAuctionId] = useState<string | null>(null);

  const auctions = auctionsQuery.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("nav.buyer.discover")}
        description={t("landing.howStep2Body")}
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label={t("nav.buyer.auctions")}
          value={auctions.length}
          icon={<Gavel className="h-5 w-5" />}
        />
        <StatCard
          label={t("nav.buyer.bids")}
          value={auctions.reduce((sum, a) => sum + a.my_bid_revisions.length, 0)}
          icon={<TrendingUp className="h-5 w-5" />}
        />
        <StatCard
          label={t("nav.buyer.reliability")}
          value="100 / 100"
          icon={<Shield className="h-5 w-5" />}
        />
      </div>

      {auctionsQuery.isPending ? (
        <LoadingSkeleton rows={2} />
      ) : auctionsQuery.isError ? (
        <ErrorState
          message={auctionsQuery.error.message}
          onRetry={() => void auctionsQuery.refetch()}
        />
      ) : auctions.length === 0 ? (
        <EmptyState title={t("landing.liveListingsEmpty")} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {auctions.map((auction) => (
            <Card key={auction.id} className="space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="text-lg font-bold text-brand-ink">
                    {auction.approx_location_label}
                  </h3>
                  <p className="text-sm text-brand-ink-muted">
                    <QuantityDisplay grams={auction.available_quantity_grams} /> •{" "}
                    <CurrencyDisplay paise={auction.min_bid_paise_per_kg} suffix="/ kg" />
                  </p>
                </div>
                <AuctionStatus status={auction.status} endsAtUtc={auction.ends_at} />
              </div>

              <Button
                className="w-full"
                variant={selectedAuctionId === auction.id ? "outline" : "default"}
                onClick={() =>
                  setSelectedAuctionId(
                    selectedAuctionId === auction.id ? null : auction.id,
                  )
                }
              >
                {t("auction.submitBid")}
              </Button>
            </Card>
          ))}
        </div>
      )}

      {selectedAuctionId ? <LiveAuctionView auctionId={selectedAuctionId} /> : null}
      <ProduceMap />
    </div>
  );
}

function BuyerSectionPlaceholder({ titleKey }: { titleKey: string }) {
  const { t } = useTranslation();
  return (
    <div>
      <PageHeader title={t(titleKey)} />
      <EmptyState
        title={t("common.noRecords")}
        description={t("common.pendingPhaseNote")}
      />
    </div>
  );
}

export function BuyerDashboard() {
  return (
    <Routes>
      <Route index element={<BuyerDiscoveryHome />} />
      <Route path="auctions" element={<BuyerDiscoveryHome />} />
      <Route path="bids" element={<BuyerDiscoveryHome />} />
      <Route path="commitments" element={<BuyerSectionPlaceholder titleKey="nav.buyer.commitments" />} />
      <Route path="orders" element={<BuyerSectionPlaceholder titleKey="nav.buyer.orders" />} />
      <Route path="reliability" element={<BuyerSectionPlaceholder titleKey="nav.buyer.reliability" />} />
    </Routes>
  );
}
