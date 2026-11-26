import { Bell, CheckCircle2 } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  useAcknowledgeNotificationMutation,
  useMyNotificationsQuery,
} from "@/hooks/queries";

export function NotificationCenter() {
  const query = useMyNotificationsQuery();
  const ackMutation = useAcknowledgeNotificationMutation();
  const [browserPermission, setBrowserPermission] = useState<string>(
    typeof Notification !== "undefined" ? Notification.permission : "unsupported",
  );

  async function enableBrowserAlerts() {
    if (typeof Notification === "undefined") return;
    const perm = await Notification.requestPermission();
    setBrowserPermission(perm);
  }

  const items = query.data ?? [];

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Bell className="h-5 w-5 text-brand-primary" />
          <h3 className="text-base font-bold text-brand-ink">Notifications & Alerts</h3>
        </div>
        {browserPermission !== "unsupported" && browserPermission !== "granted" && (
          <Button variant="outline" size="sm" onClick={() => void enableBrowserAlerts()}>
            Enable Browser Notifications
          </Button>
        )}
      </div>

      {query.isPending ? (
        <LoadingSkeleton rows={2} />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState title="No notifications yet." />
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <div
              key={item.id}
              className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-brand-border bg-brand-surface p-3"
            >
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-brand-ink">{item.title}</span>
                  <Badge
                    className={
                      item.status === "FAILED"
                        ? "border-amber-300 bg-amber-50 text-amber-900"
                        : "border-brand-border bg-brand-background text-brand-ink-muted"
                    }
                  >
                    {item.channel} · {item.status}
                  </Badge>
                </div>
                <p className="text-xs text-brand-ink-muted">{item.body}</p>
                {item.provider_message && (
                  <p className="text-xs text-amber-800">{item.provider_message}</p>
                )}
              </div>
              {item.status !== "ACKNOWLEDGED" && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => ackMutation.mutate(item.id)}
                  disabled={ackMutation.isPending}
                >
                  <CheckCircle2 className="mr-1 h-4 w-4" />
                  Acknowledge
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
