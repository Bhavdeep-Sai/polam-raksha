import { MapPin } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { CountdownTimer } from "@/components/common/CountdownTimer";
import { CurrencyDisplay } from "@/components/common/CurrencyDisplay";
import { QuantityDisplay } from "@/components/common/QuantityDisplay";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Card } from "@/components/ui/card";

interface ProduceCardProps {
  title: string;
  status: string;
  availableGrams: number;
  floorPricePaisePerKg: number;
  approxLocation: string;
  spoilageDeadlineUtc: string;
  isSimulated?: boolean;
  actions?: ReactNode;
}

export function ProduceCard({
  title,
  status,
  availableGrams,
  floorPricePaisePerKg,
  approxLocation,
  spoilageDeadlineUtc,
  isSimulated = false,
  actions,
}: ProduceCardProps) {
  const { t } = useTranslation();

  return (
    <Card className="flex flex-col justify-between gap-4">
      <div className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="text-lg font-bold text-brand-ink">{title}</h3>
            <p className="mt-1 flex items-center gap-1.5 text-sm text-brand-ink-muted">
              <MapPin className="h-4 w-4 shrink-0 text-brand-primary" aria-hidden="true" />
              <span>{approxLocation}</span>
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {isSimulated ? (
              <span className="rounded border border-brand-accent bg-amber-50 px-2 py-0.5 text-xs font-bold text-amber-950">
                {t("common.simulatedLabel")}
              </span>
            ) : null}
            <StatusBadge status={status} />
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-3 rounded-lg border border-brand-border bg-brand-bg p-3 text-sm">
          <div>
            <dt className="text-xs font-semibold text-brand-ink-muted">
              {t("listing.availableQty")}
            </dt>
            <dd className="mt-0.5 text-base font-bold text-brand-ink">
              <QuantityDisplay grams={availableGrams} />
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold text-brand-ink-muted">
              {t("listing.floorPrice")}
            </dt>
            <dd className="mt-0.5 text-base font-bold text-brand-primary">
              <CurrencyDisplay paise={floorPricePaisePerKg} suffix="/ kg" />
            </dd>
          </div>
        </dl>

        <CountdownTimer targetUtcIso={spoilageDeadlineUtc} />
      </div>

      {actions ? <div className="pt-1">{actions}</div> : null}
    </Card>
  );
}

