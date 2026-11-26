import { AlertTriangle, RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ title, message, onRetry }: ErrorStateProps) {
  const { t } = useTranslation();

  return (
    <Card
      role="alert"
      className="border-red-800/40 bg-red-50/70 text-red-950"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-700" aria-hidden="true" />
          <div>
            <h3 className="text-base font-bold">
              {title ?? t("common.errorTitle")}
            </h3>
            <p className="mt-1 text-sm text-red-900">{message}</p>
          </div>
        </div>
        {onRetry ? (
          <Button variant="outline" onClick={onRetry} className="shrink-0">
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            {t("retry")}
          </Button>
        ) : null}
      </div>
    </Card>
  );
}

