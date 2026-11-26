import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, RotateCcw, Sparkles } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiClient, ApiError } from "@/services/api";

export function DemoControlPanel() {
  const queryClient = useQueryClient();
  const statusQuery = useQuery({
    queryKey: ["admin", "demo", "status"],
    queryFn: apiClient.getDemoStatus,
  });

  const [auctionId, setAuctionId] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (statusQuery.isError || !statusQuery.data?.demo_mode_enabled) {
    // Never expose demo controls when DEMO_MODE_ENABLED=false or in production
    return null;
  }

  async function runStep(label: string, fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      const result = await fn();
      setLog((prev) => [`${label}: ${JSON.stringify(result)}`, ...prev]);
      void queryClient.invalidateQueries();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Demo step failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="space-y-4 border-amber-400 bg-amber-50/50">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-amber-800" aria-hidden="true" />
          <h3 className="text-base font-bold text-amber-950">
            Admin Demo Controls (300 kg Tomato Live Scenario)
          </h3>
        </div>
        <Badge className="border-amber-400 bg-amber-100 text-amber-950">
          DEMO DATA · {statusQuery.data.demo_auction_duration_seconds}s window
        </Badge>
      </div>

      {error ? (
        <p role="alert" className="text-xs font-semibold text-red-700">
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          disabled={busy}
          onClick={() =>
            void runStep("1. Started 300 kg Demo Listing", async () => {
              const res = await apiClient.startDemoScenario();
              setAuctionId(res.auction_id);
              return res;
            })
          }
        >
          <Play className="mr-1 h-4 w-4" aria-hidden="true" />
          1. Start 300 kg Scenario
        </Button>

        <Button
          size="sm"
          variant="outline"
          disabled={busy || !auctionId}
          onClick={() =>
            auctionId &&
            void runStep("2. Simulated 3+ Buyer Bids", () =>
              apiClient.simulateDemoBids(auctionId),
            )
          }
        >
          2. Simulate Bids (3+ Buyers)
        </Button>

        <Button
          size="sm"
          variant="outline"
          disabled={busy || !auctionId}
          onClick={() =>
            auctionId &&
            void runStep("3. Closed Auction & Ran CP-SAT", () =>
              apiClient.advanceDemoAllocate(auctionId),
            )
          }
        >
          3. Close & Allocate (CP-SAT)
        </Button>

        <Button
          size="sm"
          variant="outline"
          disabled={busy || !auctionId}
          onClick={() =>
            auctionId &&
            void runStep("4. Simulated Cancellation & Recovery", () =>
              apiClient.simulateDemoCancellation(auctionId),
            )
          }
        >
          4. Cancel 1 Order & Recover
        </Button>

        <Button
          size="sm"
          variant="outline"
          disabled={busy || !auctionId}
          onClick={() =>
            auctionId &&
            void runStep("5. Recorded Collection", () =>
              apiClient.recordDemoCollection(auctionId),
            )
          }
        >
          5. Record Collection
        </Button>

        <Button
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() =>
            void runStep("Reset Simulated Demo Data", async () => {
              setAuctionId(null);
              return apiClient.resetDemoScenario();
            })
          }
        >
          <RotateCcw className="mr-1 h-4 w-4" aria-hidden="true" />
          Reset Demo Data Only
        </Button>
      </div>

      {log.length > 0 ? (
        <ul className="space-y-1 rounded-md border border-amber-300 bg-white p-3 font-mono text-xs text-brand-ink">
          {log.map((entry, idx) => (
            <li key={idx}>{entry}</li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

