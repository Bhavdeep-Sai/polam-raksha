import { Wifi, WifiOff } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { AuctionStatus } from "@/components/common/AuctionStatus";
import { BidForm } from "@/components/common/BidForm";
import { CurrencyDisplay } from "@/components/common/CurrencyDisplay";
import { DataTable } from "@/components/common/DataTable";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { QuantityDisplay } from "@/components/common/QuantityDisplay";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Card } from "@/components/ui/card";
import { useAuctionDetailQuery, usePlaceBidMutation } from "@/hooks/queries";
import { useAuctionWebSocket } from "@/hooks/useAuctionWebSocket";
import { useNetworkStatus } from "@/hooks/useNetworkStatus";
import { formatIstDateTime } from "@/lib/format";
import { ApiError, type BidRevisionPublicResponse } from "@/services/api";

interface LiveAuctionViewProps {
  auctionId: string;
}

export function LiveAuctionView({ auctionId }: LiveAuctionViewProps) {
  const { t, i18n } = useTranslation();
  const { isOnline } = useNetworkStatus();
  const auctionQuery = useAuctionDetailQuery(auctionId);
  const placeBidMutation = usePlaceBidMutation(auctionId);
  const { connectionState, lastEvent } = useAuctionWebSocket(auctionId);
  const [bidError, setBidError] = useState<string | null>(null);

  if (auctionQuery.isPending) {
    return <LoadingSkeleton rows={3} />;
  }

  if (auctionQuery.isError) {
    return (
      <ErrorState
        message={auctionQuery.error.message}
        onRetry={() => void auctionQuery.refetch()}
      />
    );
  }

  const auction = auctionQuery.data;

  const handleBidSubmit = async (values: {
    bidPricePaisePerKg: number;
    requestedQuantityGrams: number;
    minAcceptableGrams: number;
  }) => {
    setBidError(null);
    if (!isOnline) {
      setBidError(
        "You are offline. Time-sensitive auction bids cannot be queued or submitted offline.",
      );
      return;
    }
    const idempotencyKey =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `bid-${Date.now()}`;

    try {
      await placeBidMutation.mutateAsync({
        bid_price_paise_per_kg: values.bidPricePaisePerKg,
        requested_quantity_grams: values.requestedQuantityGrams,
        min_acceptable_grams: values.minAcceptableGrams,
        estimated_collection_at: auction.spoilage_deadline_at,
        transport_responsibility: "BUYER_PICKUP",
        estimated_transport_cost_paise: 0,
        standby_until: auction.spoilage_deadline_at,
        idempotency_key: idempotencyKey,
      });
    } catch (err) {
      setBidError(err instanceof ApiError ? err.message : t("common.errorTitle"));
    }
  };

  return (
    <div className="space-y-6">
      {/* Connection & Soft-Close Banners */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-brand-border bg-brand-surface px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          {connectionState === "connected" ? (
            <>
              <Wifi className="h-4 w-4 text-green-700" aria-hidden="true" />
              <span className="text-green-900">{t("auction.liveStreamConnected")}</span>
            </>
          ) : (
            <>
              <WifiOff className="h-4 w-4 text-amber-800" aria-hidden="true" />
              <span className="text-amber-900">
                {connectionState === "reconnecting"
                  ? t("auction.liveStreamReconnecting")
                  : t("auction.liveStreamStale")}
              </span>
            </>
          )}
        </div>
        <span className="text-xs font-medium text-brand-ink-muted">
          v{auction.version} • {formatIstDateTime(auction.server_time_utc, i18n.language)}
        </span>
      </div>

      {lastEvent?.event_type === "AUCTION_SOFT_CLOSED" || auction.soft_close_extended_seconds > 0 ? (
        <div
          role="status"
          className="rounded-lg border border-amber-800/30 bg-amber-100 p-3 text-sm font-semibold text-amber-950"
        >
          {t("auction.softCloseNotice")}
        </div>
      ) : null}

      {/* Authoritative Auction Summary */}
      <Card className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-brand-ink">
              {auction.approx_location_label}
            </h2>
            <p className="text-xs text-brand-ink-muted">
              {t("auction.serverSyncedCountdown")}
            </p>
          </div>
          <AuctionStatus status={auction.status} endsAtUtc={auction.ends_at} />
        </div>

        <dl className="grid gap-3 rounded-lg border border-brand-border bg-brand-bg p-4 sm:grid-cols-3">
          <div>
            <dt className="text-xs font-semibold text-brand-ink-muted">
              {t("listing.availableQty")}
            </dt>
            <dd className="text-lg font-bold text-brand-ink">
              <QuantityDisplay grams={auction.available_quantity_grams} />
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold text-brand-ink-muted">
              {t("listing.floorPrice")}
            </dt>
            <dd className="text-lg font-bold text-brand-ink">
              <CurrencyDisplay paise={auction.min_bid_paise_per_kg} suffix="/ kg" />
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold text-brand-ink-muted">
              {t("auction.highestUnitPrice")}
            </dt>
            <dd className="text-lg font-bold text-brand-primary">
              {auction.highest_unit_price_paise_per_kg ? (
                <CurrencyDisplay
                  paise={auction.highest_unit_price_paise_per_kg}
                  suffix="/ kg"
                />
              ) : (
                "—"
              )}
            </dd>
          </div>
        </dl>

        <p className="text-xs text-brand-ink-muted">{t("auction.allocationNote")}</p>
      </Card>

      {/* Bid Submission Form */}
      <Card className="space-y-4">
        <h3 className="text-lg font-bold text-brand-ink">{t("auction.submitBid")}</h3>
        {!isOnline ? (
          <div
            role="alert"
            className="rounded-lg border border-amber-400 bg-amber-50 p-3 text-xs font-semibold text-amber-950"
          >
            Offline — Live auction bids cannot be queued or submitted without an active connection.
          </div>
        ) : null}
        {bidError ? <ErrorState message={bidError} /> : null}
        <BidForm
          minBidPaisePerKg={auction.min_bid_paise_per_kg}
          disabled={
            !isOnline ||
            placeBidMutation.isPending ||
            (auction.status !== "OPEN" && auction.status !== "CLOSING")
          }
          onSubmitBid={(vals) => void handleBidSubmit(vals)}
        />
      </Card>

      {/* Eligible Active Offers */}
      <section className="space-y-3">
        <h3 className="text-lg font-bold text-brand-ink">
          {t("auction.activeOffersTitle")}
        </h3>
        <DataTable<BidRevisionPublicResponse>
          columns={[
            { key: "alias", header: "Buyer", render: (row) => row.buyer_alias },
            {
              key: "price",
              header: "Price / kg",
              render: (row) => <CurrencyDisplay paise={row.bid_price_paise_per_kg} />,
            },
            {
              key: "qty",
              header: "Requested",
              render: (row) => <QuantityDisplay grams={row.requested_quantity_grams} />,
            },
            {
              key: "status",
              header: "Revision",
              render: (row) => (
                <StatusBadge
                  status={row.is_active ? "ACTIVE" : "CLOSED"}
                  labelOverride={`Rev #${row.revision_number}`}
                />
              ),
            },
          ]}
          rows={auction.active_offers}
          getRowKey={(row) => row.id}
          emptyTitle={t("common.noRecords")}
        />
      </section>

      {/* My Bid Revision History */}
      <section className="space-y-3">
        <h3 className="text-lg font-bold text-brand-ink">
          {t("auction.myRevisionsTitle")}
        </h3>
        <DataTable<BidRevisionPublicResponse>
          columns={[
            { key: "rev", header: "Rev", render: (row) => `#${row.revision_number}` },
            {
              key: "price",
              header: "Price / kg",
              render: (row) => <CurrencyDisplay paise={row.bid_price_paise_per_kg} />,
            },
            {
              key: "qty",
              header: "Requested",
              render: (row) => <QuantityDisplay grams={row.requested_quantity_grams} />,
            },
            {
              key: "time",
              header: "Submitted (IST)",
              render: (row) => formatIstDateTime(row.created_at, i18n.language),
            },
          ]}
          rows={auction.my_bid_revisions}
          getRowKey={(row) => row.id}
          emptyTitle={t("common.noRecords")}
        />
      </section>
    </div>
  );
}

