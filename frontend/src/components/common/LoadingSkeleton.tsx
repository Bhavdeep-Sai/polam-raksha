import { cn } from "@/lib/utils";

interface LoadingSkeletonProps {
  rows?: number;
  className?: string;
}

export function LoadingSkeleton({ rows = 3, className }: LoadingSkeletonProps) {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Loading"
      className={cn("space-y-3", className)}
    >
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={index}
          className="h-14 w-full rounded-lg border border-brand-border bg-brand-muted/70"
        />
      ))}
    </div>
  );
}

