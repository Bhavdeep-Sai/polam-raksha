import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

export function useNetworkStatus() {
  const queryClient = useQueryClient();
  const [isOnline, setIsOnline] = useState<boolean>(
    typeof navigator !== "undefined" ? navigator.onLine : true,
  );
  const [lastSyncedAt, setLastSyncedAt] = useState<string>(() => new Date().toISOString());

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      setLastSyncedAt(new Date().toISOString());
      // Refresh authoritative server state (auctions, listings, notifications) upon reconnection
      void queryClient.invalidateQueries();
    };
    const handleOffline = () => {
      setIsOnline(false);
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [queryClient]);

  const markSynced = () => {
    setLastSyncedAt(new Date().toISOString());
  };

  return { isOnline, lastSyncedAt, markSynced };
}

