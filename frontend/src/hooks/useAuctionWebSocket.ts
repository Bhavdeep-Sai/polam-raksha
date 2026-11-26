import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { queryKeys } from "@/hooks/queries";
import { env } from "@/lib/env";
import { getAccessToken, type AuctionEventEnvelope } from "@/services/api";

export type WsConnectionState = "connecting" | "connected" | "reconnecting" | "stale";

export function useAuctionWebSocket(auctionId: string | null) {
  const queryClient = useQueryClient();
  const [connectionState, setConnectionState] = useState<WsConnectionState>("connecting");
  const [serverOffsetMs, setServerOffsetMs] = useState<number>(0);
  const [lastEvent, setLastEvent] = useState<AuctionEventEnvelope | null>(null);
  const lastVersionRef = useRef<number>(0);

  useEffect(() => {
    if (!auctionId) return;
    const token = getAccessToken();
    if (!token) {
      setConnectionState("stale");
      return;
    }

    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let closedByUser = false;
    let attempt = 0;

    const connect = () => {
      const wsBase = env.VITE_WS_BASE_URL.replace(/\/$/, "");
      const url = `${wsBase}/ws/auctions/${encodeURIComponent(auctionId)}?token=${encodeURIComponent(token)}`;
      setConnectionState(attempt === 0 ? "connecting" : "reconnecting");
      ws = new WebSocket(url);

      ws.onopen = () => {
        attempt = 0;
        setConnectionState("connected");
      };

      ws.onmessage = (msg) => {
        try {
          const envelope = JSON.parse(String(msg.data)) as AuctionEventEnvelope;
          const serverMs = new Date(envelope.server_timestamp).getTime();
          if (!Number.isNaN(serverMs)) {
            setServerOffsetMs(serverMs - Date.now());
          }
          if (envelope.entity_version >= lastVersionRef.current) {
            lastVersionRef.current = envelope.entity_version;
            setLastEvent(envelope);
            void queryClient.invalidateQueries({
              queryKey: queryKeys.auctions.detail(auctionId),
            });
          }
        } catch {
          // Ignore malformed frame without crashing stream.
        }
      };

      ws.onclose = () => {
        if (closedByUser) return;
        attempt += 1;
        setConnectionState(attempt > 3 ? "stale" : "reconnecting");
        const delayMs = Math.min(10_000, 1000 * attempt);
        reconnectTimer = window.setTimeout(connect, delayMs);
      };
    };

    connect();

    return () => {
      closedByUser = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [auctionId, queryClient]);

  return { connectionState, serverOffsetMs, lastEvent };
}

