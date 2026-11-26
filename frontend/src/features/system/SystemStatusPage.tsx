import { RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";

import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useHealthQuery, useReadinessQuery } from "@/hooks/queries";
import { formatIstDateTime } from "@/lib/format";

export function SystemStatusPage() {
  const { t, i18n } = useTranslation();
  const healthQuery = useHealthQuery();
  const readinessQuery = useReadinessQuery();

  const refetchAll = () => {
    void healthQuery.refetch();
    void readinessQuery.refetch();
  };

  return (
    <div>
      <PageHeader
        title={t("systemStatus")}
        description={t("foundationNote")}
        actions={
          <Button variant="outline" onClick={refetchAll}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            {t("retry")}
          </Button>
        }
      />

      {healthQuery.isPending || readinessQuery.isPending ? (
        <LoadingSkeleton rows={2} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <Card className="space-y-3">
            <h2 className="text-base font-bold text-brand-ink">{t("backendApi")}</h2>
            {healthQuery.isError ? (
              <ErrorState
                message={healthQuery.error.message}
                onRetry={() => void healthQuery.refetch()}
              />
            ) : (
              <div className="space-y-2">
                <StatusBadge status="CONNECTED" labelOverride={t("connected")} />
                <p className="text-xs text-brand-ink-muted">
                  {formatIstDateTime(healthQuery.data.timestamp_utc, i18n.language)}
                </p>
              </div>
            )}
          </Card>

          <Card className="space-y-3">
            <h2 className="text-base font-bold text-brand-ink">{t("databaseReadiness")}</h2>
            {readinessQuery.isError ? (
              <ErrorState
                message={readinessQuery.error.message}
                onRetry={() => void readinessQuery.refetch()}
              />
            ) : (
              <div className="space-y-2">
                <StatusBadge status="READY" labelOverride={t("ready")} />
                <p className="text-xs text-brand-ink-muted">
                  {formatIstDateTime(readinessQuery.data.timestamp_utc, i18n.language)}
                </p>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

