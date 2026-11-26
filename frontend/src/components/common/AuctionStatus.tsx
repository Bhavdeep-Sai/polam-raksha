import { CountdownTimer } from "@/components/common/CountdownTimer";
import { StatusBadge } from "@/components/common/StatusBadge";

interface AuctionStatusProps {
  status: string;
  endsAtUtc: string;
}

export function AuctionStatus({ status, endsAtUtc }: AuctionStatusProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <StatusBadge status={status} />
      <CountdownTimer targetUtcIso={endsAtUtc} />
    </div>
  );
}

