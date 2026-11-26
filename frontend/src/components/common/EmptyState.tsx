import { Inbox } from "lucide-react";
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <Card className="flex flex-col items-center justify-center py-10 text-center">
      <div
        aria-hidden="true"
        className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-brand-muted text-brand-primary"
      >
        <Inbox className="h-6 w-6" />
      </div>
      <h3 className="text-lg font-bold text-brand-ink">{title}</h3>
      {description ? (
        <p className="mt-1 max-w-md text-sm text-brand-ink-muted">{description}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </Card>
  );
}

