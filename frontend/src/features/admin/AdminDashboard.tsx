import { Activity, AlertTriangle, CheckCircle2, ShieldAlert, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Route, Routes } from "react-router-dom";

import { CurrencyDisplay } from "@/components/common/CurrencyDisplay";
import { DataTable } from "@/components/common/DataTable";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DemoControlPanel } from "@/features/admin/DemoControlPanel";
import { ImpactAnalyticsView } from "@/features/analytics/ImpactAnalyticsView";
import { NotificationCenter } from "@/features/notifications/NotificationCenter";
import {
  useAdminAllocationRunsQuery,
  useAdminAuditEventsQuery,
  useAdminDisputesQuery,
  useAdminOverviewQuery,
  useAdminUsersQuery,
  useOperatorPermissionsQuery,
  useResolveDisputeMutation,
  useRevokeOperatorPermissionMutation,
  useVerifyBuyerMutation,
} from "@/hooks/queries";
import type {
  AdminUserSummary,
  AllocationRunResponse,
  AuditEventSummary,
  DisputeCaseSummary,
  OperatorPermissionSummary,
} from "@/services/api";

function AdminOperationsView() {
  const { t } = useTranslation();
  const overviewQuery = useAdminOverviewQuery();
  const usersQuery = useAdminUsersQuery();
  const permsQuery = useOperatorPermissionsQuery();
  const disputesQuery = useAdminDisputesQuery();
  const verifyBuyer = useVerifyBuyerMutation();
  const revokePerm = useRevokeOperatorPermissionMutation();
  const resolveDispute = useResolveDisputeMutation();

  const ov = overviewQuery.data;

  return (
    <div className="space-y-6">
      <PageHeader title={t("nav.admin.users")} />
      <DemoControlPanel />
      {overviewQuery.isPending ? (
        <LoadingSkeleton rows={2} />
      ) : overviewQuery.isError ? (
        <ErrorState
          message={overviewQuery.error.message}
          onRetry={() => void overviewQuery.refetch()}
        />
      ) : ov ? (
        <>
          <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <StatCard label="Active Auctions" value={ov.active_auctions_count} icon={<Activity className="h-5 w-5" />} />
            <StatCard label="Pending Confirm" value={ov.pending_confirmations_count} icon={<Users className="h-5 w-5" />} />
            <StatCard label="Expired Listings" value={ov.expired_listings_count} icon={<AlertTriangle className="h-5 w-5" />} />
            <StatCard label="Failed Collect" value={ov.failed_collections_count} icon={<ShieldAlert className="h-5 w-5" />} />
            <StatCard label="Recovery Events" value={ov.recovery_events_count} icon={<CheckCircle2 className="h-5 w-5" />} />
            <StatCard label="Open Disputes" value={ov.open_disputes_count} icon={<AlertTriangle className="h-5 w-5" />} />
          </div>

          <Card className="space-y-3">
            <h3 className="text-base font-bold text-brand-ink">Worker & External Integration Health</h3>
            <p className="text-xs text-brand-ink-muted">
              Pending Jobs: {ov.pending_jobs_count} · Failed Jobs: {ov.failed_jobs_count} ·
              Unpublished Outbox Events: {ov.unpublished_outbox_count}
            </p>
            <div className="grid gap-2 sm:grid-cols-3">
              {ov.integrations.map((item) => (
                <div
                  key={item.name}
                  className="rounded-lg border border-brand-border bg-brand-surface p-3 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-brand-ink">{item.name}</span>
                    <Badge
                      className={
                        item.configured
                          ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                          : "border-brand-border bg-brand-background text-brand-ink-muted"
                      }
                    >
                      {item.mode}
                    </Badge>
                  </div>
                  <p className="mt-1 text-brand-ink-muted">{item.detail}</p>
                </div>
              ))}
            </div>
          </Card>
        </>
      ) : null}

      <Card className="space-y-3">
        <h3 className="text-base font-bold text-brand-ink">Users & Buyer Verification</h3>
        {usersQuery.isPending ? (
          <LoadingSkeleton rows={3} />
        ) : (
          <DataTable<AdminUserSummary>
            columns={[
              { key: "name", header: "Name", render: (u) => u.full_name },
              { key: "role", header: "Role", render: (u) => u.role },
              { key: "district", header: "District", render: (u) => u.district ?? "—" },
              {
                key: "verification",
                header: "Verification",
                render: (u) => u.verification_status ?? (u.is_active ? "ACTIVE" : "INACTIVE"),
              },
              {
                key: "action",
                header: "Review",
                render: (u) =>
                  u.role === "BUYER" ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        verifyBuyer.mutate({
                          buyerId: u.id,
                          payload: { verification_status: "VERIFIED", is_restricted: false },
                        })
                      }
                    >
                      Verify Buyer
                    </Button>
                  ) : (
                    "—"
                  ),
              },
            ]}
            rows={usersQuery.data ?? []}
            getRowKey={(u) => u.id}
            emptyTitle={t("common.noRecords")}
          />
        )}
      </Card>

      <Card className="space-y-3">
        <h3 className="text-base font-bold text-brand-ink">Operator Permissions</h3>
        <DataTable<OperatorPermissionSummary>
          columns={[
            { key: "op", header: "Operator", render: (p) => p.operator_name },
            { key: "farmer", header: "Farmer", render: (p) => p.farmer_name },
            { key: "method", header: "Consent", render: (p) => p.consent_method },
            {
              key: "status",
              header: "Status",
              render: (p) => (p.is_active ? "ACTIVE" : "REVOKED"),
            },
            {
              key: "action",
              header: "Action",
              render: (p) =>
                p.is_active ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => revokePerm.mutate(p.id)}
                  >
                    Revoke
                  </Button>
                ) : (
                  "—"
                ),
            },
          ]}
          rows={permsQuery.data ?? []}
          getRowKey={(p) => p.id}
          emptyTitle={t("common.noRecords")}
        />
      </Card>

      <Card className="space-y-3">
        <h3 className="text-base font-bold text-brand-ink">Dispute Review</h3>
        <DataTable<DisputeCaseSummary>
          columns={[
            { key: "reason", header: "Reason", render: (d) => d.reason },
            { key: "status", header: "Status", render: (d) => d.status },
            {
              key: "action",
              header: "Resolution",
              render: (d) =>
                d.status !== "RESOLVED" ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      resolveDispute.mutate({
                        disputeId: d.id,
                        payload: {
                          status: "RESOLVED",
                          resolution_notes: "Reviewed and resolved by admin",
                        },
                      })
                    }
                  >
                    Mark Resolved
                  </Button>
                ) : (
                  d.resolution_notes ?? "Resolved"
                ),
            },
          ]}
          rows={disputesQuery.data ?? []}
          getRowKey={(d) => d.id}
          emptyTitle={t("common.noRecords")}
        />
      </Card>

      <NotificationCenter />
    </div>
  );
}

function AdminRunsView({ titleKey }: { titleKey: string }) {
  const { t } = useTranslation();
  const runsQuery = useAdminAllocationRunsQuery();
  const runs = runsQuery.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title={t(titleKey)} />
      {runsQuery.isPending ? (
        <LoadingSkeleton rows={2} />
      ) : runsQuery.isError ? (
        <ErrorState message={runsQuery.error.message} onRetry={() => void runsQuery.refetch()} />
      ) : (
        <DataTable<AllocationRunResponse>
          columns={[
            {
              key: "solver",
              header: "Solver",
              render: (row) => `${row.solver_status} (${row.algorithm_version})`,
            },
            { key: "strategy", header: "Strategy", render: (row) => row.strategy },
            {
              key: "net",
              header: "Est. Net Sales Revenue",
              render: (row) => <CurrencyDisplay paise={row.estimated_net_revenue_paise} />,
            },
            {
              key: "approved",
              header: "Approval",
              render: (row) => (
                <StatusBadge status={row.is_approved ? "CONFIRMED" : "PENDING_CONFIRMATION"} />
              ),
            },
          ]}
          rows={runs}
          getRowKey={(row) => row.id}
          emptyTitle={t("common.noRecords")}
        />
      )}
    </div>
  );
}

function AdminAuditView() {
  const { t } = useTranslation();
  const auditQuery = useAdminAuditEventsQuery();

  return (
    <div className="space-y-6">
      <PageHeader title={t("nav.admin.audit")} />
      {auditQuery.isPending ? (
        <LoadingSkeleton rows={4} />
      ) : auditQuery.isError ? (
        <ErrorState message={auditQuery.error.message} onRetry={() => void auditQuery.refetch()} />
      ) : (
        <DataTable<AuditEventSummary>
          columns={[
            { key: "action", header: "Action", render: (e) => e.action },
            { key: "resource", header: "Resource", render: (e) => `${e.resource_type} (${e.resource_id ?? "—"})` },
            { key: "actor", header: "Actor", render: (e) => e.actor_user_id?.slice(0, 8) ?? "system" },
            { key: "time", header: "UTC Time", render: (e) => e.created_at },
          ]}
          rows={auditQuery.data ?? []}
          getRowKey={(e) => e.id}
          emptyTitle={t("common.noRecords")}
        />
      )}
    </div>
  );
}

function AdminAnalyticsPage() {
  const { t } = useTranslation();
  return (
    <div className="space-y-6">
      <PageHeader title={t("nav.admin.analytics")} />
      <ImpactAnalyticsView />
    </div>
  );
}

export function AdminDashboard() {
  return (
    <Routes>
      <Route index element={<AdminOperationsView />} />
      <Route path="auctions" element={<AdminRunsView titleKey="nav.admin.auctions" />} />
      <Route
        path="failed-collections"
        element={<AdminRunsView titleKey="nav.admin.failedCollections" />}
      />
      <Route path="recovery" element={<AdminRunsView titleKey="nav.admin.recovery" />} />
      <Route path="analytics" element={<AdminAnalyticsPage />} />
      <Route path="audit" element={<AdminAuditView />} />
    </Routes>
  );
}
