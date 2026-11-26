import { useQueryClient } from "@tanstack/react-query";
import { Download, RefreshCw, Wifi, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { useNetworkStatus } from "@/hooks/useNetworkStatus";
import { formatIstDateTime } from "@/lib/format";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function PwaStatusBar() {
  const { i18n } = useTranslation();
  const queryClient = useQueryClient();
  const { isOnline, lastSyncedAt, markSynced } = useNetworkStatus();
  const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [updateReady, setUpdateReady] = useState(false);
  const [swUpdater, setSwUpdater] = useState<((reloadPage?: boolean) => Promise<void>) | null>(null);

  const isIos =
    typeof navigator !== "undefined" &&
    /iPad|iPhone|iPod/.test(navigator.userAgent) &&
    !(window.navigator as Navigator & { standalone?: boolean }).standalone;

  useEffect(() => {
    const onBeforeInstall = (event: Event) => {
      event.preventDefault();
      setInstallPrompt(event as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", onBeforeInstall);

    // Register service worker in browser builds; safely ignored in Vitest/JSDOM
    if (typeof window !== "undefined" && "serviceWorker" in navigator) {
      void import("virtual:pwa-register")
        .then(({ registerSW }) => {
          const updateSW = registerSW({
            onNeedRefresh() {
              setUpdateReady(true);
            },
          });
          setSwUpdater(() => updateSW);
        })
        .catch(() => {
          // Ignore when running outside Vite PWA build
        });
    }

    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
    };
  }, []);

  const handleRetrySync = () => {
    void queryClient.invalidateQueries().then(() => {
      markSynced();
    });
  };

  const handleInstall = async () => {
    if (!installPrompt) return;
    await installPrompt.prompt();
    setInstallPrompt(null);
  };

  return (
    <div
      role="status"
      aria-live="polite"
      className={
        isOnline
          ? "border-b border-brand-border bg-brand-surface px-4 py-1.5 text-xs text-brand-ink-muted"
          : "border-b border-amber-400 bg-amber-50 px-4 py-2 text-xs font-semibold text-amber-950"
      }
    >
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {isOnline ? (
            <>
              <Wifi className="h-3.5 w-3.5 text-green-700" aria-hidden="true" />
              <span>
                Online · Last synced: {formatIstDateTime(lastSyncedAt, i18n.language)}
              </span>
            </>
          ) : (
            <>
              <WifiOff className="h-3.5 w-3.5 text-amber-800" aria-hidden="true" />
              <span>
                Offline Mode — Cached app shell active. Data may be stale; live bids and approvals
                require internet.
              </span>
            </>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {!isOnline && (
            <Button
              size="sm"
              variant="outline"
              onClick={handleRetrySync}
              className="min-h-8 px-2.5 py-1 text-xs"
            >
              <RefreshCw className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
              Retry Sync
            </Button>
          )}
          {installPrompt && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => void handleInstall()}
              className="min-h-8 px-2.5 py-1 text-xs"
            >
              <Download className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
              Install App
            </Button>
          )}
          {!installPrompt && isIos && (
            <span className="text-[11px] text-brand-ink-muted">
              iOS: Tap Share → Add to Home Screen
            </span>
          )}
          {updateReady && swUpdater && (
            <Button
              size="sm"
              onClick={() => void swUpdater(true)}
              className="min-h-8 px-2.5 py-1 text-xs"
            >
              Update Available — Reload
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

