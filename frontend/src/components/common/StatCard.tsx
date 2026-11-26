import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";

interface StatCardProps {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: ReactNode;
}

export function StatCard({ label, value, hint, icon }: StatCardProps) {
  return (
    <Card className="flex flex-col justify-between gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-brand-ink-muted">{label}</span>
        {icon ? (
          <span className="text-brand-primary" aria-hidden="true">
            {icon}
          </span>
        ) : null}
      </div>
      <div className="text-2xl font-bold text-brand-ink">{value}</div>
      {hint ? <p className="text-xs text-brand-ink-muted">{hint}</p> : null}
    </Card>
  );
}

