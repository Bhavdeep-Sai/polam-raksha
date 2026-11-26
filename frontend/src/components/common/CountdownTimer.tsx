import { Clock } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { computeCountdown } from "@/lib/format";
import { cn } from "@/lib/utils";

interface CountdownTimerProps {
  targetUtcIso: string;
  className?: string;
}

export function CountdownTimer({ targetUtcIso, className }: CountdownTimerProps) {
  const { t } = useTranslation();
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const { hours, minutes, isUrgent, isExpired } = computeCountdown(targetUtcIso, nowMs);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-sm font-semibold",
        isExpired ? "text-red-800" : isUrgent ? "text-amber-900" : "text-brand-ink",
        className,
      )}
    >
      <Clock className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span>
        {isExpired
          ? t("status.EXPIRED")
          : t("common.timeRemaining", { hours, minutes })}
      </span>
    </span>
  );
}

