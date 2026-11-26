import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { List, Map as MapIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { CurrencyDisplay } from "@/components/common/CurrencyDisplay";
import { DataTable } from "@/components/common/DataTable";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { QuantityDisplay } from "@/components/common/QuantityDisplay";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useMapPointsQuery } from "@/hooks/queries";
import type { MapPointResponse } from "@/services/api";

export function ProduceMap() {
  const { t } = useTranslation();
  const pointsQuery = useMapPointsQuery();
  const isOnline = typeof navigator !== "undefined" ? navigator.onLine : true;
  const [viewMode, setViewMode] = useState<"map" | "list">(isOnline ? "map" : "list");
  const containerRef = useRef<HTMLDivElement>(null);

  const points = pointsQuery.data ?? [];

  useEffect(() => {
    if (viewMode !== "map" || !containerRef.current || points.length === 0) return;

    const first = points[0];
    if (!first) return;
    const map = L.map(containerRef.current).setView([first.latitude, first.longitude], 10);

    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 18,
    }).addTo(map);

    for (const pt of points) {
      L.circleMarker([pt.latitude, pt.longitude], {
        radius: pt.is_exact ? 9 : 12,
        color: pt.is_exact ? "#205438" : "#548C55",
        fillOpacity: 0.5,
      })
        .bindPopup(
          `<strong>${pt.label}</strong><br/>${pt.is_exact && pt.exact_pickup_address ? pt.exact_pickup_address : "Approximate location"}`,
        )
        .addTo(map);
    }

    return () => {
      map.remove();
    };
  }, [viewMode, points]);

  if (pointsQuery.isPending) return <LoadingSkeleton rows={2} />;
  if (pointsQuery.isError) {
    return (
      <ErrorState
        message={pointsQuery.error.message}
        onRetry={() => void pointsQuery.refetch()}
      />
    );
  }

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-bold text-brand-ink">
          Produce Locations ({isOnline ? "Online" : "Offline List Fallback"})
        </h3>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setViewMode(viewMode === "map" ? "list" : "map")}
        >
          {viewMode === "map" ? (
            <>
              <List className="h-4 w-4" aria-hidden="true" />
              List View
            </>
          ) : (
            <>
              <MapIcon className="h-4 w-4" aria-hidden="true" />
              Map View
            </>
          )}
        </Button>
      </div>

      {viewMode === "map" && isOnline && points.length > 0 ? (
        <div
          ref={containerRef}
          className="h-72 w-full rounded-lg border border-brand-border"
          aria-label="Produce locations map"
        />
      ) : (
        <DataTable<MapPointResponse>
          columns={[
            { key: "label", header: "Location", render: (row) => row.label },
            {
              key: "precision",
              header: "Precision",
              render: (row) =>
                row.is_exact && row.exact_pickup_address
                  ? `Confirmed Pickup: ${row.exact_pickup_address}`
                  : "Approximate Area",
            },
            {
              key: "qty",
              header: "Available",
              render: (row) => <QuantityDisplay grams={row.available_quantity_grams} />,
            },
            {
              key: "price",
              header: "Floor / kg",
              render: (row) => <CurrencyDisplay paise={row.floor_price_paise_per_kg} />,
            },
          ]}
          rows={points}
          getRowKey={(row) => row.listing_id}
          emptyTitle={t("common.noRecords")}
        />
      )}
    </Card>
  );
}

