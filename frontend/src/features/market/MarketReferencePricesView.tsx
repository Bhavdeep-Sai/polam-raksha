import { useTranslation } from "react-i18next";

import { CurrencyDisplay } from "@/components/common/CurrencyDisplay";
import { DataTable } from "@/components/common/DataTable";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Card } from "@/components/ui/card";
import { useMarketPricesQuery } from "@/hooks/queries";
import { formatIstDateTime } from "@/lib/format";
import type { MarketPriceResponse } from "@/services/api";

export function MarketReferencePricesView() {
  const { t, i18n } = useTranslation();
  const pricesQuery = useMarketPricesQuery();
  const isTelugu = i18n.language.startsWith("te");

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("nav.farmer.prices")}
        description="Reference prices are historical/external observations only and are not guaranteed selling prices."
      />

      {pricesQuery.isPending ? (
        <LoadingSkeleton rows={3} />
      ) : pricesQuery.isError ? (
        <ErrorState
          message={pricesQuery.error.message}
          onRetry={() => void pricesQuery.refetch()}
        />
      ) : (
        <Card className="space-y-4">
          <DataTable<MarketPriceResponse>
            columns={[
              {
                key: "commodity",
                header: "Commodity",
                render: (row) =>
                  isTelugu ? row.commodity_name_te : row.commodity_name_en,
              },
              {
                key: "market",
                header: "Market",
                render: (row) => `${row.market_name}, ${row.district}`,
              },
              {
                key: "price_kg",
                header: "Normalized / kg",
                render: (row) => (
                  <CurrencyDisplay paise={row.normalized_price_paise_per_kg} />
                ),
              },
              {
                key: "freshness",
                header: "Freshness",
                render: (row) => (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <StatusBadge
                      status={row.is_stale ? "EXPIRED" : "ACTIVE"}
                      labelOverride={row.is_stale ? "Stale" : "Recent"}
                    />
                    {row.is_simulated ? (
                      <span className="rounded border border-brand-accent bg-amber-50 px-1.5 py-0.5 text-xs font-bold">
                        {t("common.simulatedLabel")}
                      </span>
                    ) : null}
                  </div>
                ),
              },
              {
                key: "observed",
                header: "Observed (IST)",
                render: (row) => formatIstDateTime(row.observed_at, i18n.language),
              },
            ]}
            rows={pricesQuery.data}
            getRowKey={(row) => row.id}
            emptyTitle={t("common.noRecords")}
          />
        </Card>
      )}
    </div>
  );
}

