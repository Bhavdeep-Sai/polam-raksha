import { AlertTriangle, CheckCircle2, Clock, Info, XCircle } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { getStatusMeta, STATUS_TONE_CLASSES } from "@/lib/status";

interface StatusBadgeProps {
  status: string;
  labelOverride?: string;
}

const ICONS = {
  check: CheckCircle2,
  clock: Clock,
  alert: AlertTriangle,
  info: Info,
  x: XCircle,
};

export function StatusBadge({ status, labelOverride }: StatusBadgeProps) {
  const { t } = useTranslation();
  const meta = getStatusMeta(status);
  const Icon = ICONS[meta.icon];
  const label = labelOverride ?? t(meta.labelKey, { defaultValue: status });

  return (
    <Badge className={STATUS_TONE_CLASSES[meta.tone]}>
      <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>{label}</span>
    </Badge>
  );
}

