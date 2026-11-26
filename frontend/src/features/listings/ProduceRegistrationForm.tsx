import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarClock, Save, Sprout } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { AccessibleFormField } from "@/components/common/AccessibleFormField";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { CurrencyDisplay } from "@/components/common/CurrencyDisplay";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { VoicePrompt } from "@/components/common/VoicePrompt";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  useCreateListingMutation,
  useCropsQuery,
  useSchedulePreviewMutation,
} from "@/hooks/queries";
import { useNetworkStatus } from "@/hooks/useNetworkStatus";
import { formatIstDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ApiError, type SchedulePreviewResponse } from "@/services/api";

const listingSchema = z.object({
  crop_id: z.string().uuid("Select a crop"),
  quantity_value: z.coerce.number().positive(),
  quantity_unit: z.enum(["KG", "QUINTAL"]),
  floor_price_rupees_per_kg: z.coerce.number().positive(),
  quality_grade: z.enum(["GRADE_A", "GRADE_B", "STANDARD"]),
  harvested_at_local: z.string().min(1),
  urgency_option: z.enum(["WITHIN_2H", "WITHIN_6H", "WITHIN_12H", "WITHIN_24H", "CUSTOM"]),
  custom_deadline_local: z.string().optional(),
  transport_responsibility: z.enum(["BUYER_PICKUP", "FARMER_DELIVERY", "SHARED"]),
  auto_allocate_approved: z.boolean(),
  approx_location_label: z.string().min(2),
  exact_pickup_address: z.string().min(3),
  photo_url: z.string().optional(),
});

type ListingFormValues = z.infer<typeof listingSchema>;

interface ProduceRegistrationFormProps {
  farmerId?: string;
  consentConfirmed?: boolean;
  onSuccess?: () => void;
}

const URGENCY_OPTIONS = [
  { value: "WITHIN_2H", labelKey: "farmerForm.urgency2h" },
  { value: "WITHIN_6H", labelKey: "farmerForm.urgency6h" },
  { value: "WITHIN_12H", labelKey: "farmerForm.urgency12h" },
  { value: "WITHIN_24H", labelKey: "farmerForm.urgency24h" },
  { value: "CUSTOM", labelKey: "farmerForm.urgencyCustom" },
] as const;

const OFFLINE_DRAFT_STORAGE_KEY = "polam_offline_listing_draft_v1";

export function ProduceRegistrationForm({
  farmerId,
  consentConfirmed = true,
  onSuccess,
}: ProduceRegistrationFormProps) {
  const { t, i18n } = useTranslation();
  const isTelugu = i18n.language.startsWith("te");
  const { isOnline } = useNetworkStatus();

  const cropsQuery = useCropsQuery();
  const previewMutation = useSchedulePreviewMutation();
  const createMutation = useCreateListingMutation();

  const [schedulePreview, setSchedulePreview] = useState<SchedulePreviewResponse | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingValues, setPendingValues] = useState<ListingFormValues | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);
  const [hasLocalDraft, setHasLocalDraft] = useState<boolean>(() => {
    try {
      return typeof localStorage !== "undefined" && Boolean(localStorage.getItem(OFFLINE_DRAFT_STORAGE_KEY));
    } catch {
      return false;
    }
  });

  const defaultHarvestLocal = new Date(Date.now() - 3_600_000).toISOString().slice(0, 16);

  const {
    register,
    setValue,
    watch,
    getValues,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ListingFormValues>({
    resolver: zodResolver(listingSchema),
    defaultValues: {
      crop_id: "",
      quantity_value: 50,
      quantity_unit: "KG",
      floor_price_rupees_per_kg: 20,
      quality_grade: "GRADE_A",
      harvested_at_local: defaultHarvestLocal,
      urgency_option: "WITHIN_12H",
      transport_responsibility: "BUYER_PICKUP",
      auto_allocate_approved: false,
      approx_location_label: "",
      exact_pickup_address: "",
      photo_url: "",
    },
  });

  useEffect(() => {
    try {
      const raw = localStorage.getItem(OFFLINE_DRAFT_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<ListingFormValues>;
        reset({ ...getValues(), ...parsed });
        setHasLocalDraft(true);
      }
    } catch {
      // Ignore corrupt local draft
    }
  }, [getValues, reset]);

  const handleSaveOfflineDraft = () => {
    try {
      localStorage.setItem(OFFLINE_DRAFT_STORAGE_KEY, JSON.stringify(getValues()));
      setHasLocalDraft(true);
      setApiError(null);
    } catch {
      setApiError("Unable to save local offline draft in browser storage.");
    }
  };

  const handleClearOfflineDraft = () => {
    try {
      localStorage.removeItem(OFFLINE_DRAFT_STORAGE_KEY);
    } catch {
      // Ignore
    }
    setHasLocalDraft(false);
  };

  const selectedCropId = watch("crop_id");
  const quantityValue = watch("quantity_value") || 0;
  const quantityUnit = watch("quantity_unit");
  const floorRupees = watch("floor_price_rupees_per_kg") || 0;
  const urgencyOption = watch("urgency_option");
  const customDeadlineLocal = watch("custom_deadline_local");

  const storedGrams = Math.round(
    quantityValue * (quantityUnit === "QUINTAL" ? 100_000 : 1000),
  );
  const floorPaisePerKg = Math.round(floorRupees * 100);
  const estimatedGrossPaise = Math.round((storedGrams / 1000) * floorPaisePerKg);

  const handlePreviewSchedule = async () => {
    setApiError(null);
    try {
      const res = await previewMutation.mutateAsync({
        urgency_option: urgencyOption,
        custom_collection_deadline_at:
          urgencyOption === "CUSTOM" && customDeadlineLocal
            ? new Date(customDeadlineLocal).toISOString()
            : null,
      });
      setSchedulePreview(res);
    } catch (err) {
      setApiError(err instanceof ApiError ? err.message : t("common.errorTitle"));
    }
  };

  const handlePrepareConfirm = async (values: ListingFormValues) => {
    setApiError(null);
    setSuccessNotice(null);
    try {
      const preview = await previewMutation.mutateAsync({
        urgency_option: values.urgency_option,
        custom_collection_deadline_at:
          values.urgency_option === "CUSTOM" && values.custom_deadline_local
            ? new Date(values.custom_deadline_local).toISOString()
            : null,
      });
      setSchedulePreview(preview);
      setPendingValues(values);
      setConfirmOpen(true);
    } catch (err) {
      setApiError(err instanceof ApiError ? err.message : t("common.errorTitle"));
    }
  };

  const handleConfirmPublish = async () => {
    if (!pendingValues) return;
    setConfirmOpen(false);
    setApiError(null);
    try {
      await createMutation.mutateAsync({
        farmer_id: farmerId ?? null,
        crop_id: pendingValues.crop_id,
        quantity_value: pendingValues.quantity_value,
        quantity_unit: pendingValues.quantity_unit,
        floor_price_paise_per_kg: Math.round(pendingValues.floor_price_rupees_per_kg * 100),
        harvested_at: new Date(pendingValues.harvested_at_local).toISOString(),
        spoilage_deadline_at:
          pendingValues.urgency_option === "CUSTOM" && pendingValues.custom_deadline_local
            ? new Date(pendingValues.custom_deadline_local).toISOString()
            : null,
        urgency_option: pendingValues.urgency_option,
        quality_grade: pendingValues.quality_grade,
        photo_urls: pendingValues.photo_url?.trim() ? [pendingValues.photo_url.trim()] : [],
        transport_responsibility: pendingValues.transport_responsibility,
        auto_allocate_approved: pendingValues.auto_allocate_approved,
        approx_location_label: pendingValues.approx_location_label,
        exact_pickup_address: pendingValues.exact_pickup_address,
        consent_confirmed: consentConfirmed,
      });
      setSuccessNotice(t("farmerForm.listingCreated"));
      setSchedulePreview(null);
      setPendingValues(null);
      handleClearOfflineDraft();
      reset();
      onSuccess?.();
    } catch (err) {
      setApiError(err instanceof ApiError ? err.message : t("common.errorTitle"));
    }
  };

  return (
    <Card className="space-y-5">
      {apiError ? <ErrorState message={apiError} /> : null}
      {successNotice ? (
        <div
          role="status"
          className="rounded-lg border border-green-800/30 bg-green-100 p-3 text-sm font-semibold text-green-950"
        >
          {successNotice}
        </div>
      ) : null}

      <form onSubmit={handleSubmit(handlePrepareConfirm)} className="space-y-5">
        {/* Bilingual Large Crop Selector */}
        <div className="space-y-2">
          <span className="block text-sm font-semibold text-brand-ink">
            {t("farmerForm.selectCrop")} <span className="text-red-700">*</span>
          </span>
          {cropsQuery.isPending ? (
            <LoadingSkeleton rows={1} />
          ) : cropsQuery.isError ? (
            <ErrorState
              message={cropsQuery.error.message}
              onRetry={() => void cropsQuery.refetch()}
            />
          ) : (
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
              {cropsQuery.data.map((crop) => {
                const active = selectedCropId === crop.id;
                return (
                  <button
                    key={crop.id}
                    type="button"
                    onClick={() => setValue("crop_id", crop.id, { shouldValidate: true })}
                    className={cn(
                      "flex min-h-14 flex-col items-start justify-center rounded-lg border-2 px-3.5 py-2.5 text-left transition-colors",
                      active
                        ? "border-brand-primary bg-brand-primary text-white"
                        : "border-brand-border bg-brand-bg text-brand-ink hover:bg-brand-muted",
                    )}
                  >
                    <span className="text-base font-bold">
                      {isTelugu ? crop.name_te : crop.name_en}
                    </span>
                    <span className={cn("text-xs", active ? "text-white/90" : "text-brand-ink-muted")}>
                      {isTelugu ? crop.name_en : crop.name_te}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
          {errors.crop_id ? (
            <p role="alert" className="text-sm font-medium text-red-800">
              {errors.crop_id.message}
            </p>
          ) : null}
        </div>

        {/* Quantity & Unit + Floor Price */}
        <div className="grid gap-4 sm:grid-cols-3">
          <AccessibleFormField
            id="listing-qty"
            label={t("farmerForm.quantityLabel")}
            hint={t("farmerForm.storedGramsHint", { grams: storedGrams })}
            error={errors.quantity_value?.message}
            required
          >
            <Input
              id="listing-qty"
              type="number"
              inputMode="decimal"
              step="0.5"
              min="1"
              {...register("quantity_value")}
            />
          </AccessibleFormField>

          <AccessibleFormField
            id="listing-unit"
            label={t("farmerForm.unitLabel")}
            required
          >
            <select
              id="listing-unit"
              className="min-h-11 w-full rounded-lg border-2 border-brand-border bg-white px-3 py-2 text-base text-brand-ink"
              {...register("quantity_unit")}
            >
              <option value="KG">{t("farmerForm.unitKg")}</option>
              <option value="QUINTAL">{t("farmerForm.unitQuintal")}</option>
            </select>
          </AccessibleFormField>

          <AccessibleFormField
            id="listing-floor"
            label={t("farmerForm.floorPriceLabel")}
            error={errors.floor_price_rupees_per_kg?.message}
            required
          >
            <Input
              id="listing-floor"
              type="number"
              inputMode="decimal"
              step="0.5"
              min="1"
              {...register("floor_price_rupees_per_kg")}
            />
          </AccessibleFormField>
        </div>

        {/* Estimated Gross Value Preview */}
        <div className="rounded-lg border border-brand-border bg-brand-bg p-3 text-sm">
          <span className="font-semibold text-brand-ink-muted">
            {t("farmerForm.estimatedNetRevenue")}:{" "}
          </span>
          <CurrencyDisplay
            paise={estimatedGrossPaise}
            className="text-base font-bold text-brand-primary"
          />
        </div>

        {/* Urgency Selection */}
        <div className="space-y-2">
          <span className="block text-sm font-semibold text-brand-ink">
            {t("farmerForm.urgencyLabel")} <span className="text-red-700">*</span>
          </span>
          <p className="text-xs text-brand-ink-muted">{t("farmerForm.urgencyNote")}</p>
          <div className="flex flex-wrap gap-2">
            {URGENCY_OPTIONS.map((opt) => {
              const active = urgencyOption === opt.value;
              return (
                <Button
                  key={opt.value}
                  variant={active ? "default" : "outline"}
                  size="sm"
                  onClick={() => setValue("urgency_option", opt.value)}
                >
                  {t(opt.labelKey)}
                </Button>
              );
            })}
          </div>
        </div>

        {urgencyOption === "CUSTOM" ? (
          <AccessibleFormField
            id="listing-custom-deadline"
            label={t("farmerForm.customDeadlineLabel")}
            required
          >
            <Input
              id="listing-custom-deadline"
              type="datetime-local"
              {...register("custom_deadline_local")}
            />
          </AccessibleFormField>
        ) : null}

        {/* Grade, Harvest Time, Transport */}
        <div className="grid gap-4 sm:grid-cols-3">
          <AccessibleFormField
            id="listing-grade"
            label={t("farmerForm.qualityLabel")}
          >
            <select
              id="listing-grade"
              className="min-h-11 w-full rounded-lg border-2 border-brand-border bg-white px-3 py-2 text-base text-brand-ink"
              {...register("quality_grade")}
            >
              <option value="GRADE_A">{t("farmerForm.gradeA")}</option>
              <option value="GRADE_B">{t("farmerForm.gradeB")}</option>
              <option value="STANDARD">{t("farmerForm.gradeStandard")}</option>
            </select>
          </AccessibleFormField>

          <AccessibleFormField
            id="listing-harvested"
            label={t("farmerForm.harvestedAtLabel")}
            required
          >
            <Input
              id="listing-harvested"
              type="datetime-local"
              {...register("harvested_at_local")}
            />
          </AccessibleFormField>

          <AccessibleFormField
            id="listing-transport"
            label={t("farmerForm.transportLabel")}
          >
            <select
              id="listing-transport"
              className="min-h-11 w-full rounded-lg border-2 border-brand-border bg-white px-3 py-2 text-base text-brand-ink"
              {...register("transport_responsibility")}
            >
              <option value="BUYER_PICKUP">{t("farmerForm.transportBuyer")}</option>
              <option value="FARMER_DELIVERY">{t("farmerForm.transportFarmer")}</option>
              <option value="SHARED">{t("farmerForm.transportShared")}</option>
            </select>
          </AccessibleFormField>
        </div>

        {/* Location & Optional Photo */}
        <div className="grid gap-4 sm:grid-cols-2">
          <AccessibleFormField
            id="listing-approx-loc"
            label={t("farmerForm.approxLocationLabel")}
            error={errors.approx_location_label?.message}
            required
          >
            <Input
              id="listing-approx-loc"
              placeholder="Tadikonda Mandal, Guntur"
              {...register("approx_location_label")}
            />
          </AccessibleFormField>

          <AccessibleFormField
            id="listing-pickup-addr"
            label={t("farmerForm.pickupAddressLabel")}
            error={errors.exact_pickup_address?.message}
            required
          >
            <Input
              id="listing-pickup-addr"
              {...register("exact_pickup_address")}
            />
          </AccessibleFormField>
        </div>

        <AccessibleFormField
          id="listing-photo"
          label={t("farmerForm.photoUrlLabel")}
        >
          <Input id="listing-photo" type="url" {...register("photo_url")} />
        </AccessibleFormField>

        <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border border-brand-border bg-brand-bg px-3 py-2 text-sm font-medium text-brand-ink">
          <input
            type="checkbox"
            className="h-5 w-5 accent-brand-primary"
            {...register("auto_allocate_approved")}
          />
          <span>{t("farmerForm.autoAllocateLabel")}</span>
        </label>

        {/* Schedule Read-Back Preview */}
        {schedulePreview ? (
          <div className="space-y-2 rounded-lg border-2 border-brand-primary/30 bg-brand-muted/50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-sm font-bold text-brand-ink">
                {t("farmerForm.schedulePreviewTitle")}
              </h4>
              <VoicePrompt
                text={t("farmerForm.confirmBody", {
                  biddingClose: formatIstDateTime(
                    schedulePreview.hard_bidding_close_at,
                    i18n.language,
                  ),
                  collectionDeadline: formatIstDateTime(
                    schedulePreview.collection_deadline_at,
                    i18n.language,
                  ),
                })}
              />
            </div>
            <p className="text-sm text-brand-ink">
              <strong>{t("farmerForm.biddingHardClose")}:</strong>{" "}
              {formatIstDateTime(schedulePreview.hard_bidding_close_at, i18n.language)}
            </p>
            <p className="text-sm text-brand-ink">
              <strong>{t("farmerForm.collectionDeadline")}:</strong>{" "}
              {formatIstDateTime(schedulePreview.collection_deadline_at, i18n.language)}
            </p>
            {schedulePreview.is_direct_offer_mode ? (
              <p className="text-xs font-bold text-amber-900">
                {t("farmerForm.directOfferMode")}
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={handleSaveOfflineDraft}
          >
            <Save className="h-4 w-4" aria-hidden="true" />
            Save Local Draft
          </Button>
          <Button
            variant="outline"
            onClick={() => void handlePreviewSchedule()}
            disabled={!isOnline || previewMutation.isPending}
          >
            <CalendarClock className="h-4 w-4" aria-hidden="true" />
            {t("farmerForm.previewSchedule")}
          </Button>
          <Button
            type="submit"
            size="lg"
            disabled={!isOnline || createMutation.isPending || previewMutation.isPending}
          >
            <Sprout className="h-5 w-5" aria-hidden="true" />
            {t("farmerForm.submitListing")}
          </Button>
        </div>
        {hasLocalDraft ? (
          <div
            role="status"
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-400 bg-amber-50 p-3 text-xs font-semibold text-amber-950"
          >
            <span>
              Local Offline Draft Saved — This draft is NOT a published listing. Connect to the
              internet to publish.
            </span>
            <Button type="button" size="sm" variant="outline" onClick={handleClearOfflineDraft}>
              Discard Draft
            </Button>
          </div>
        ) : null}
      </form>

      <ConfirmDialog
        open={confirmOpen}
        title={t("farmerForm.confirmTitle")}
        description={
          schedulePreview
            ? t("farmerForm.confirmBody", {
                biddingClose: formatIstDateTime(
                  schedulePreview.hard_bidding_close_at,
                  i18n.language,
                ),
                collectionDeadline: formatIstDateTime(
                  schedulePreview.collection_deadline_at,
                  i18n.language,
                ),
              })
            : ""
        }
        onConfirm={() => void handleConfirmPublish()}
        onCancel={() => setConfirmOpen(false)}
      />
    </Card>
  );
}

