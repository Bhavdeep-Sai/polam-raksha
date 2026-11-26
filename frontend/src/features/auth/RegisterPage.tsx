import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { AccessibleFormField } from "@/components/common/AccessibleFormField";
import { ErrorState } from "@/components/common/ErrorState";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useRegisterMutation } from "@/hooks/queries";
import { ApiError } from "@/services/api";

const registerSchema = z.object({
  full_name: z.string().min(2),
  role: z.enum(["FARMER", "BUYER"]),
  phone_number: z.string().min(10).max(20),
  email: z.string().optional(),
  password: z.string().min(8),
  village: z.string().optional(),
  mandal: z.string().optional(),
  district: z.string().optional(),
  exact_pickup_address: z.string().optional(),
  business_name: z.string().optional(),
});

type RegisterValues = z.infer<typeof registerSchema>;

export function RegisterPage() {
  const { t, i18n } = useTranslation();
  const [searchParams] = useSearchParams();
  const initialRole = searchParams.get("role") === "BUYER" ? "BUYER" : "FARMER";
  const registerMutation = useRegisterMutation();
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const {
    register,
    watch,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      role: initialRole,
    },
  });

  const selectedRole = watch("role");

  const onSubmit = async (values: RegisterValues) => {
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await registerMutation.mutateAsync({
        full_name: values.full_name,
        role: values.role,
        phone_number: values.phone_number,
        email: values.email?.trim() ? values.email.trim() : null,
        password: values.password,
        preferred_language: i18n.language.startsWith("te") ? "te" : "en",
        village: values.village || null,
        mandal: values.mandal || null,
        district: values.district || null,
        exact_pickup_address: values.exact_pickup_address || null,
        business_name: values.business_name || null,
        buyer_type: values.role === "BUYER" ? "wholesaler" : null,
      });
      setSuccessMsg(t("auth.registerSuccess"));
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : t("common.errorTitle"));
    }
  };

  return (
    <div className="mx-auto max-w-xl">
      <PageHeader
        title={t("auth.registerTitle")}
        description={t("auth.registerSubtitle")}
      />

      {errorMsg ? (
        <div className="mb-4">
          <ErrorState message={errorMsg} />
        </div>
      ) : null}

      {successMsg ? (
        <Card className="mb-4 border-green-800/40 bg-green-50 text-green-950">
          <p className="font-semibold">{successMsg}</p>
          <Link
            to="/login"
            className="mt-2 inline-block font-bold text-brand-primary underline"
          >
            {t("nav.login")}
          </Link>
        </Card>
      ) : null}

      <Card>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <AccessibleFormField
            id="reg-role"
            label={t("auth.roleLabel")}
            error={errors.role?.message}
            required
          >
            <select
              id="reg-role"
              className="min-h-11 w-full rounded-lg border-2 border-brand-border bg-white px-3 py-2 text-base text-brand-ink focus:border-brand-primary focus:outline-none"
              {...register("role")}
            >
              <option value="FARMER">{t("roles.FARMER")}</option>
              <option value="BUYER">{t("roles.BUYER")}</option>
            </select>
          </AccessibleFormField>

          <AccessibleFormField
            id="reg-name"
            label={t("auth.fullNameLabel")}
            error={errors.full_name?.message}
            required
          >
            <Input id="reg-name" {...register("full_name")} />
          </AccessibleFormField>

          <div className="grid gap-4 sm:grid-cols-2">
            <AccessibleFormField
              id="reg-phone"
              label={t("auth.phoneLabel")}
              error={errors.phone_number?.message}
              required
            >
              <Input id="reg-phone" type="tel" {...register("phone_number")} />
            </AccessibleFormField>

            <AccessibleFormField
              id="reg-email"
              label={t("auth.emailLabel")}
              error={errors.email?.message}
            >
              <Input id="reg-email" type="email" {...register("email")} />
            </AccessibleFormField>
          </div>

          <AccessibleFormField
            id="reg-password"
            label={t("auth.passwordLabel")}
            error={errors.password?.message}
            required
          >
            <Input id="reg-password" type="password" {...register("password")} />
          </AccessibleFormField>

          {selectedRole === "FARMER" ? (
            <div className="space-y-4 border-t border-brand-border pt-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <AccessibleFormField id="reg-village" label={t("auth.villageLabel")}>
                  <Input id="reg-village" {...register("village")} />
                </AccessibleFormField>
                <AccessibleFormField id="reg-mandal" label={t("auth.mandalLabel")}>
                  <Input id="reg-mandal" {...register("mandal")} />
                </AccessibleFormField>
                <AccessibleFormField id="reg-district" label={t("auth.districtLabel")}>
                  <Input id="reg-district" {...register("district")} />
                </AccessibleFormField>
              </div>
              <AccessibleFormField id="reg-address" label={t("auth.addressLabel")}>
                <Input id="reg-address" {...register("exact_pickup_address")} />
              </AccessibleFormField>
            </div>
          ) : (
            <div className="grid gap-4 border-t border-brand-border pt-4 sm:grid-cols-2">
              <AccessibleFormField id="reg-business" label={t("auth.businessNameLabel")}>
                <Input id="reg-business" {...register("business_name")} />
              </AccessibleFormField>
              <AccessibleFormField id="reg-buyer-district" label={t("auth.districtLabel")}>
                <Input id="reg-buyer-district" {...register("district")} />
              </AccessibleFormField>
            </div>
          )}

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {t("auth.createAccountButton")}
          </Button>
        </form>
      </Card>
    </div>
  );
}
