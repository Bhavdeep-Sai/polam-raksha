import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import { AccessibleFormField } from "@/components/common/AccessibleFormField";
import { ErrorState } from "@/components/common/ErrorState";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getDefaultRouteForRole, useAuth } from "@/features/auth/AuthContext";
import { ApiError } from "@/services/api";

const passwordSchema = z.object({
  identifier: z.string().min(3),
  password: z.string().min(1),
});

const pinSchema = z.object({
  phone_number: z.string().min(10).max(20),
  pin: z.string().regex(/^\d{4,6}$/, "PIN must be 4 to 6 digits"),
});

type PasswordValues = z.infer<typeof passwordSchema>;
type PinValues = z.infer<typeof pinSchema>;

export function LoginPage() {
  const { t } = useTranslation();
  const { loginWithPassword, loginWithPin } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"password" | "pin">("password");
  const [apiError, setApiError] = useState<string | null>(null);

  const pwForm = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
  });

  const pinForm = useForm<PinValues>({
    resolver: zodResolver(pinSchema),
  });

  const handlePasswordSubmit = async (values: PasswordValues) => {
    setApiError(null);
    try {
      const user = await loginWithPassword(values);
      navigate(getDefaultRouteForRole(user.role));
    } catch (err) {
      setApiError(err instanceof ApiError ? err.message : t("common.errorTitle"));
    }
  };

  const handlePinSubmit = async (values: PinValues) => {
    setApiError(null);
    try {
      const user = await loginWithPin(values);
      navigate(getDefaultRouteForRole(user.role));
    } catch (err) {
      setApiError(err instanceof ApiError ? err.message : t("common.errorTitle"));
    }
  };

  return (
    <div className="mx-auto max-w-lg">
      <PageHeader
        title={t("auth.loginTitle")}
        description={t("auth.loginSubtitle")}
      />

      <div className="mb-4 flex gap-2" role="tablist" aria-label={t("auth.loginTitle")}>
        <Button
          role="tab"
          aria-selected={mode === "password"}
          variant={mode === "password" ? "default" : "outline"}
          onClick={() => {
            setMode("password");
            setApiError(null);
          }}
        >
          {t("auth.passwordTab")}
        </Button>
        <Button
          role="tab"
          aria-selected={mode === "pin"}
          variant={mode === "pin" ? "default" : "outline"}
          onClick={() => {
            setMode("pin");
            setApiError(null);
          }}
        >
          {t("auth.pinTab")}
        </Button>
      </div>

      {apiError ? (
        <div className="mb-4">
          <ErrorState message={apiError} />
        </div>
      ) : null}

      <Card>
        {mode === "password" ? (
          <form onSubmit={pwForm.handleSubmit(handlePasswordSubmit)} className="space-y-4">
            <AccessibleFormField
              id="login-identifier"
              label={t("auth.identifierLabel")}
              error={pwForm.formState.errors.identifier?.message}
              required
            >
              <Input
                id="login-identifier"
                autoComplete="username"
                {...pwForm.register("identifier")}
              />
            </AccessibleFormField>

            <AccessibleFormField
              id="login-password"
              label={t("auth.passwordLabel")}
              error={pwForm.formState.errors.password?.message}
              required
            >
              <Input
                id="login-password"
                type="password"
                autoComplete="current-password"
                {...pwForm.register("password")}
              />
            </AccessibleFormField>

            <Button
              type="submit"
              className="w-full"
              disabled={pwForm.formState.isSubmitting}
            >
              {t("auth.signInButton")}
            </Button>
          </form>
        ) : (
          <form onSubmit={pinForm.handleSubmit(handlePinSubmit)} className="space-y-4">
            <AccessibleFormField
              id="pin-phone"
              label={t("auth.phoneLabel")}
              error={pinForm.formState.errors.phone_number?.message}
              required
            >
              <Input
                id="pin-phone"
                type="tel"
                inputMode="tel"
                placeholder="+919876543210"
                {...pinForm.register("phone_number")}
              />
            </AccessibleFormField>

            <AccessibleFormField
              id="pin-code"
              label={t("auth.pinLabel")}
              error={pinForm.formState.errors.pin?.message}
              required
            >
              <Input
                id="pin-code"
                type="password"
                inputMode="numeric"
                maxLength={6}
                {...pinForm.register("pin")}
              />
            </AccessibleFormField>

            <Button
              type="submit"
              className="w-full"
              disabled={pinForm.formState.isSubmitting}
            >
              {t("auth.signInButton")}
            </Button>
          </form>
        )}

        <p className="mt-4 text-center text-sm text-brand-ink-muted">
          <Link to="/register" className="font-semibold text-brand-primary underline">
            {t("nav.register")}
          </Link>
        </p>
      </Card>
    </div>
  );
}

