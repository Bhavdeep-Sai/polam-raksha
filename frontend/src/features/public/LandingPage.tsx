import {
  Gavel,
  PhoneCall,
  RefreshCw,
  ShieldAlert,
  Sprout,
  Truck,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ProduceCard } from "@/components/common/ProduceCard";
import { VoicePrompt } from "@/components/common/VoicePrompt";
import { Card } from "@/components/ui/card";
import { usePublicListingsQuery } from "@/hooks/queries";

export function LandingPage() {
  const { t } = useTranslation();
  const listingsQuery = usePublicListingsQuery();

  return (
    <div className="space-y-10">
      {/* Hero Section */}
      <section className="rounded-xl border-2 border-brand-primary/20 bg-brand-surface p-6 sm:p-10">
        <div className="max-w-3xl space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="inline-flex items-center gap-2 rounded-md border border-brand-accent bg-amber-50 px-3 py-1 text-xs font-bold text-brand-ink">
              <Sprout className="h-4 w-4 text-brand-primary" aria-hidden="true" />
              {t("landing.heroBadge")}
            </span>
            <VoicePrompt text={`${t("landing.heroTitle")}. ${t("landing.heroBody")}`} />
          </div>

          <h1 className="text-3xl font-bold tracking-tight text-brand-ink sm:text-4xl">
            {t("landing.heroTitle")}
          </h1>
          <p className="text-base leading-relaxed text-brand-ink-muted sm:text-lg">
            {t("landing.heroBody")}
          </p>

          <div className="flex flex-wrap gap-3 pt-2">
            <Link
              to="/register?role=FARMER"
              className="inline-flex min-h-12 items-center justify-center rounded-lg bg-brand-primary px-6 py-3 text-base font-bold text-white hover:bg-brand-primary-hover"
            >
              {t("landing.ctaFarmer")}
            </Link>
            <Link
              to="/register?role=BUYER"
              className="inline-flex min-h-12 items-center justify-center rounded-lg border-2 border-brand-primary bg-white px-6 py-3 text-base font-bold text-brand-primary hover:bg-brand-muted"
            >
              {t("landing.ctaBuyer")}
            </Link>
            <Link
              to="/login"
              className="inline-flex min-h-12 items-center justify-center rounded-lg px-5 py-3 text-base font-semibold text-brand-ink hover:bg-brand-muted"
            >
              {t("landing.ctaLogin")}
            </Link>
          </div>
        </div>
      </section>

      {/* Problem & Accessibility */}
      <section className="grid gap-5 md:grid-cols-2">
        <Card className="space-y-2 border-l-4 border-l-brand-accent">
          <h2 className="text-xl font-bold text-brand-ink">
            {t("landing.problemTitle")}
          </h2>
          <p className="text-sm leading-relaxed text-brand-ink-muted">
            {t("landing.problemBody")}
          </p>
        </Card>

        <Card className="space-y-2 border-l-4 border-l-brand-primary">
          <div className="flex items-center gap-2">
            <PhoneCall className="h-5 w-5 text-brand-primary" aria-hidden="true" />
            <h2 className="text-xl font-bold text-brand-ink">
              {t("landing.accessibilityTitle")}
            </h2>
          </div>
          <p className="text-sm leading-relaxed text-brand-ink-muted">
            {t("landing.accessibilityBody")}
          </p>
        </Card>
      </section>

      {/* How It Works */}
      <section aria-labelledby="how-it-works-heading" className="space-y-4">
        <h2
          id="how-it-works-heading"
          className="text-2xl font-bold text-brand-ink"
        >
          {t("landing.howTitle")}
        </h2>
        <div className="grid gap-5 md:grid-cols-3">
          <Card className="space-y-2">
            <Sprout className="h-6 w-6 text-brand-primary" aria-hidden="true" />
            <h3 className="text-lg font-bold text-brand-ink">
              {t("landing.howStep1Title")}
            </h3>
            <p className="text-sm text-brand-ink-muted">{t("landing.howStep1Body")}</p>
          </Card>

          <Card className="space-y-2">
            <div className="flex items-center gap-2 text-brand-secondary">
              <Gavel className="h-6 w-6 text-brand-primary" aria-hidden="true" />
              <Truck className="h-5 w-5" aria-hidden="true" />
            </div>
            <h3 className="text-lg font-bold text-brand-ink">
              {t("landing.howStep2Title")}
            </h3>
            <p className="text-sm text-brand-ink-muted">{t("landing.howStep2Body")}</p>
          </Card>

          <Card className="space-y-2">
            <RefreshCw className="h-6 w-6 text-brand-primary" aria-hidden="true" />
            <h3 className="text-lg font-bold text-brand-ink">
              {t("landing.howStep3Title")}
            </h3>
            <p className="text-sm text-brand-ink-muted">{t("landing.howStep3Body")}</p>
          </Card>
        </div>
      </section>

      {/* Live Public Surplus Listings */}
      <section aria-labelledby="live-listings-heading" className="space-y-4">
        <h2
          id="live-listings-heading"
          className="text-2xl font-bold text-brand-ink"
        >
          {t("landing.liveListingsTitle")}
        </h2>

        {listingsQuery.isPending ? (
          <LoadingSkeleton rows={2} />
        ) : listingsQuery.isError ? (
          <ErrorState
            message={listingsQuery.error.message}
            onRetry={() => void listingsQuery.refetch()}
          />
        ) : listingsQuery.data.length === 0 ? (
          <EmptyState title={t("landing.liveListingsEmpty")} />
        ) : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {listingsQuery.data.map((item) => (
              <ProduceCard
                key={item.id}
                title={`Crop #${item.crop_id.slice(0, 6)}`}
                status={item.status}
                availableGrams={item.available_quantity_grams}
                floorPricePaisePerKg={item.floor_price_paise_per_kg}
                approxLocation={item.approx_location_label}
                spoilageDeadlineUtc={item.spoilage_deadline_at}
                isSimulated={item.is_simulated}
              />
            ))}
          </div>
        )}
      </section>

      {/* Limitations & Contact */}
      <section className="grid gap-5 md:grid-cols-2">
        <Card className="space-y-2 bg-brand-muted/60">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-brand-ink" aria-hidden="true" />
            <h2 className="text-lg font-bold text-brand-ink">
              {t("landing.limitationsTitle")}
            </h2>
          </div>
          <p className="text-sm text-brand-ink-muted">{t("landing.limitationsBody")}</p>
        </Card>

        <Card className="space-y-2">
          <h2 className="text-lg font-bold text-brand-ink">
            {t("landing.contactTitle")}
          </h2>
          <p className="text-sm text-brand-ink-muted">{t("landing.contactBody")}</p>
        </Card>
      </section>
    </div>
  );
}

