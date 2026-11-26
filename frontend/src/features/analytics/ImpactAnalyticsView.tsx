import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CurrencyDisplay } from "@/components/common/CurrencyDisplay";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { QuantityDisplay } from "@/components/common/QuantityDisplay";
import { StatCard } from "@/components/common/StatCard";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useImpactAnalyticsQuery } from "@/hooks/queries";

export function ImpactAnalyticsView() {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [cropCode, setCropCode] = useState("");
  const [location, setLocation] = useState("");
  const [includeSimulated, setIncludeSimulated] = useState(false);

  const query = useImpactAnalyticsQuery({
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    crop_code: cropCode || undefined,
    location: location || undefined,
    include_simulated: includeSimulated,
  });

  const data = query.data;
  const prod = data?.production;

  return (
    <div className="space-y-6">
      <Card className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <label className="space-y-1 text-xs font-medium text-brand-ink-muted">
          <span>Start Date (IST)</span>
          <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </label>
        <label className="space-y-1 text-xs font-medium text-brand-ink-muted">
          <span>End Date (IST)</span>
          <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </label>
        <label className="space-y-1 text-xs font-medium text-brand-ink-muted">
          <span>Crop Code</span>
          <Input
            placeholder="e.g. TOMATO"
            value={cropCode}
            onChange={(e) => setCropCode(e.target.value)}
          />
        </label>
        <label className="space-y-1 text-xs font-medium text-brand-ink-muted">
          <span>Location</span>
          <Input
            placeholder="e.g. Guntur"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-2 pt-5 text-xs font-semibold text-brand-ink">
          <input
            type="checkbox"
            checked={includeSimulated}
            onChange={(e) => setIncludeSimulated(e.target.checked)}
          />
          <span>Show Simulated Demo Separately</span>
        </label>
      </Card>

      {query.isPending ? (
        <LoadingSkeleton rows={4} />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : !prod || !prod.has_data ? (
        <EmptyState
          title="No production impact records match these filters."
          description="Demo/simulated records are excluded from production metrics unless toggled separately."
        />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Produce Listed (kg)"
              value={<QuantityDisplay grams={prod.produce_listed_grams} />}
            />
            <StatCard
              label="Produce Allocated (kg)"
              value={<QuantityDisplay grams={prod.produce_allocated_grams} />}
            />
            <StatCard
              label="Produce Actually Collected (kg)"
              value={<QuantityDisplay grams={prod.produce_collected_grams} />}
            />
            <StatCard
              label="Rescued from Waste (Evidence-Based)"
              value={<QuantityDisplay grams={prod.rescued_from_waste_grams} />}
            />
            <StatCard
              label="Surplus Produce Collected (kg)"
              value={<QuantityDisplay grams={prod.surplus_produce_collected_grams} />}
            />
            <StatCard
              label="Cancelled / Recovered (kg)"
              value={
                <span>
                  <QuantityDisplay grams={prod.cancelled_quantity_grams} /> /{" "}
                  <QuantityDisplay grams={prod.recovered_after_cancellation_grams} />
                </span>
              }
            />
            <StatCard
              label="Gross / Est. Net Sales Revenue"
              value={
                <span>
                  <CurrencyDisplay paise={prod.gross_transaction_value_paise} /> /{" "}
                  <CurrencyDisplay paise={prod.estimated_net_sales_revenue_paise} />
                </span>
              }
            />
            <StatCard
              label="Buyer Completion Rate"
              value={
                prod.buyer_completion_rate_percent !== null
                  ? `${prod.buyer_completion_rate_percent}%`
                  : "—"
              }
            />
          </div>

          <Card className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-base font-bold text-brand-ink">
                Daily Surplus & Collection Volume (kg, IST)
              </h3>
              <Badge className="border-brand-border bg-brand-surface text-brand-ink">
                Production Only
              </Badge>
            </div>
            {data.daily_series.length === 0 ? (
              <EmptyState title="No daily time-series points available." />
            ) : (
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.daily_series}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date_ist" />
                    <YAxis unit=" kg" />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="listed_kg" name="Listed (kg)" fill="#205438" />
                    <Bar dataKey="allocated_kg" name="Allocated (kg)" fill="#D9AA44" />
                    <Bar dataKey="collected_kg" name="Collected (kg)" fill="#548C55" />
                    <Bar dataKey="cancelled_kg" name="Cancelled (kg)" fill="#B91C1C" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
            <p className="text-xs text-brand-ink-muted">{prod.methodology_note}</p>
            <p className="text-xs text-brand-ink-muted">{prod.baseline_note}</p>
          </Card>
        </div>
      )}

      {data?.demo_simulated && (
        <Card className="space-y-3 border-amber-300 bg-amber-50/40">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-amber-900">
              {data.demo_simulated.dataset_label} (Separated from Production)
            </h3>
            <Badge className="border-amber-300 bg-amber-100 text-amber-900">SIMULATED</Badge>
          </div>
          <div className="grid gap-3 sm:grid-cols-3 text-xs">
            <div>
              Listed: <QuantityDisplay grams={data.demo_simulated.produce_listed_grams} />
            </div>
            <div>
              Collected: <QuantityDisplay grams={data.demo_simulated.produce_collected_grams} />
            </div>
            <div>
              Gross Value: <CurrencyDisplay paise={data.demo_simulated.gross_transaction_value_paise} />
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
