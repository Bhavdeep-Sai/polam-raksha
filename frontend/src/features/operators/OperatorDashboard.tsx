import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Route, Routes } from "react-router-dom";
import { z } from "zod";

import { AccessibleFormField } from "@/components/common/AccessibleFormField";
import { DataTable } from "@/components/common/DataTable";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ProduceRegistrationForm } from "@/features/listings/ProduceRegistrationForm";
import {
  useAssistedOnboardMutation,
  useAssistedOverviewQuery,
} from "@/hooks/queries";
import { formatIstDateTime } from "@/lib/format";
import { ApiError } from "@/services/api";

const onboardSchema = z.object({
  full_name: z.string().min(2),
  preferred_language: z.enum(["te", "en"]),
  phone_number: z.string().optional(),
  village: z.string().min(2),
  mandal: z.string().min(2),
  district: z.string().min(2),
  exact_pickup_address: z.string().optional(),
  consent_method: z.enum(["IN_PERSON_VERBAL", "KEYPAD_PIN", "SIGNED_FORM"]),
  consent_confirmed: z.boolean().refine((val) => val === true, {
    message: "Explicit farmer consent is required",
  }),
});

type OnboardValues = z.infer<typeof onboardSchema>;

function OperatorRegisterHome() {
  const { t } = useTranslation();
  const onboardMutation = useAssistedOnboardMutation();
  const [apiError, setApiError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<OnboardValues>({
    resolver: zodResolver(onboardSchema),
    defaultValues: {
      preferred_language: "te",
      mandal: "Unspecified",
      consent_method: "IN_PERSON_VERBAL",
      consent_confirmed: false,
    },
  });

  const onSubmit = async (values: OnboardValues) => {
    setApiError(null);
    setSuccessMsg(null);
    try {
      await onboardMutation.mutateAsync({
        full_name: values.full_name,
        preferred_language: values.preferred_language,
        phone_number: values.phone_number?.trim() ? values.phone_number.trim() : null,
        village: values.village,
        mandal: values.mandal,
        district: values.district,
        exact_pickup_address: values.exact_pickup_address?.trim() || null,
        consent_method: values.consent_method,
        consent_confirmed: values.consent_confirmed,
      });
      setSuccessMsg(t("operatorForm.onboardSuccess"));
      reset();
    } catch (err) {
      setApiError(err instanceof ApiError ? err.message : t("common.errorTitle"));
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("operatorForm.onboardTitle")}
        description={t("operatorForm.onboardSubtitle")}
      />

      {apiError ? <ErrorState message={apiError} /> : null}
      {successMsg ? (
        <Card className="border-green-800/30 bg-green-100 text-green-950">
          <p className="font-semibold">{successMsg}</p>
        </Card>
      ) : null}

      <Card>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <AccessibleFormField
              id="op-farmer-name"
              label={t("auth.fullNameLabel")}
              error={errors.full_name?.message}
              required
            >
              <Input id="op-farmer-name" {...register("full_name")} />
            </AccessibleFormField>

            <AccessibleFormField
              id="op-farmer-lang"
              label={t("operatorForm.preferredLangLabel")}
            >
              <select
                id="op-farmer-lang"
                className="min-h-11 w-full rounded-lg border-2 border-brand-border bg-white px-3 py-2 text-base text-brand-ink"
                {...register("preferred_language")}
              >
                <option value="te">తెలుగు (Telugu)</option>
                <option value="en">English</option>
              </select>
            </AccessibleFormField>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <AccessibleFormField id="op-farmer-phone" label={t("auth.phoneLabel")}>
              <Input id="op-farmer-phone" type="tel" {...register("phone_number")} />
            </AccessibleFormField>

            <AccessibleFormField
              id="op-farmer-village"
              label={t("auth.villageLabel")}
              error={errors.village?.message}
              required
            >
              <Input id="op-farmer-village" {...register("village")} />
            </AccessibleFormField>

            <AccessibleFormField
              id="op-farmer-district"
              label={t("auth.districtLabel")}
              error={errors.district?.message}
              required
            >
              <Input id="op-farmer-district" {...register("district")} />
            </AccessibleFormField>
          </div>

          <AccessibleFormField
            id="op-consent-method"
            label={t("operatorForm.consentMethodLabel")}
          >
            <select
              id="op-consent-method"
              className="min-h-11 w-full rounded-lg border-2 border-brand-border bg-white px-3 py-2 text-base text-brand-ink"
              {...register("consent_method")}
            >
              <option value="IN_PERSON_VERBAL">{t("operatorForm.consentVerbal")}</option>
              <option value="KEYPAD_PIN">{t("operatorForm.consentPin")}</option>
              <option value="SIGNED_FORM">{t("operatorForm.consentSigned")}</option>
            </select>
          </AccessibleFormField>

          <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border border-brand-border bg-brand-bg px-3 py-2 text-sm font-medium text-brand-ink">
            <input
              type="checkbox"
              className="h-5 w-5 accent-brand-primary"
              {...register("consent_confirmed")}
            />
            <span>{t("operatorForm.consentCheckbox")}</span>
          </label>
          {errors.consent_confirmed ? (
            <p role="alert" className="text-sm font-medium text-red-800">
              {errors.consent_confirmed.message}
            </p>
          ) : null}

          <Button type="submit" disabled={isSubmitting}>
            {t("operatorForm.submitOnboard")}
          </Button>
        </form>
      </Card>
    </div>
  );
}

function OperatorListProduceView() {
  const { t } = useTranslation();
  const overviewQuery = useAssistedOverviewQuery();
  const [selectedFarmerId, setSelectedFarmerId] = useState<string>("");

  const farmers = overviewQuery.data?.farmers ?? [];
  const activeFarmerId = selectedFarmerId || farmers[0]?.farmer_id || "";

  return (
    <div className="space-y-6">
      <PageHeader title={t("nav.operator.listProduce")} />

      {overviewQuery.isPending ? (
        <LoadingSkeleton rows={2} />
      ) : overviewQuery.isError ? (
        <ErrorState
          message={overviewQuery.error.message}
          onRetry={() => void overviewQuery.refetch()}
        />
      ) : farmers.length === 0 ? (
        <EmptyState title={t("operatorForm.noFarmers")} />
      ) : (
        <div className="space-y-5">
          <Card>
            <AccessibleFormField
              id="op-select-farmer"
              label={t("operatorForm.selectFarmerLabel")}
              required
            >
              <select
                id="op-select-farmer"
                value={activeFarmerId}
                onChange={(e) => setSelectedFarmerId(e.target.value)}
                className="min-h-11 w-full rounded-lg border-2 border-brand-border bg-white px-3 py-2 text-base text-brand-ink"
              >
                {farmers.map((f) => (
                  <option key={f.farmer_id} value={f.farmer_id}>
                    {f.full_name} — {f.village}, {f.district}
                  </option>
                ))}
              </select>
            </AccessibleFormField>
          </Card>

          {activeFarmerId ? (
            <ProduceRegistrationForm farmerId={activeFarmerId} consentConfirmed />
          ) : null}
        </div>
      )}
    </div>
  );
}

function OperatorHistoryView() {
  const { t, i18n } = useTranslation();
  const overviewQuery = useAssistedOverviewQuery();

  return (
    <div className="space-y-6">
      <PageHeader title={t("nav.operator.history")} />
      {overviewQuery.isPending ? (
        <LoadingSkeleton rows={2} />
      ) : overviewQuery.isError ? (
        <ErrorState
          message={overviewQuery.error.message}
          onRetry={() => void overviewQuery.refetch()}
        />
      ) : (
        <DataTable
          columns={[
            { key: "action", header: "Action", render: (row) => row.action },
            {
              key: "resource",
              header: "Resource",
              render: (row) => `${row.resource_type} (${row.resource_id ?? "—"})`,
            },
            {
              key: "created_at",
              header: "Time (IST)",
              render: (row) => formatIstDateTime(row.created_at, i18n.language),
            },
          ]}
          rows={overviewQuery.data.audit_history}
          getRowKey={(row) => row.id}
          emptyTitle={t("common.noRecords")}
        />
      )}
    </div>
  );
}

export function OperatorDashboard() {
  return (
    <Routes>
      <Route index element={<OperatorRegisterHome />} />
      <Route path="list-produce" element={<OperatorListProduceView />} />
      <Route path="history" element={<OperatorHistoryView />} />
    </Routes>
  );
}
