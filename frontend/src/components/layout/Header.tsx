import { LogOut, Sprout } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { LanguageSwitcher } from "@/components/layout/LanguageSwitcher";
import { Button } from "@/components/ui/button";
import { getDefaultRouteForRole, useAuth } from "@/features/auth/AuthContext";

export function Header() {
  const { t } = useTranslation();
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  return (
    <header className="sticky top-0 z-30 border-b border-brand-border bg-brand-surface">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
        <Link
          to={user ? getDefaultRouteForRole(user.role) : "/"}
          className="flex items-center gap-3 rounded-lg focus-visible:outline-none"
        >
          <div
            aria-hidden="true"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-brand-primary text-white"
          >
            <Sprout className="h-6 w-6" />
          </div>
          <div className="min-w-0">
            <span className="block truncate text-lg font-bold tracking-tight text-brand-ink">
              {t("appName")}
            </span>
            <span className="hidden text-xs font-medium text-brand-ink-muted sm:block">
              {t("tagline")}
            </span>
          </div>
        </Link>

        <div className="flex flex-wrap items-center gap-2">
          <LanguageSwitcher />
          {isAuthenticated && user ? (
            <div className="flex items-center gap-2">
              <span className="hidden rounded-md border border-brand-border bg-brand-muted px-2.5 py-1 text-xs font-bold text-brand-ink sm:inline-block">
                {user.full_name} ({t(`roles.${user.role}`)})
              </span>
              <Button variant="ghost" size="sm" onClick={() => void handleLogout()}>
                <LogOut className="h-4 w-4" aria-hidden="true" />
                <span className="hidden sm:inline">{t("nav.logout")}</span>
              </Button>
            </div>
          ) : (
            <div className="hidden items-center gap-2 sm:flex">
              <Link
                to="/login"
                className="inline-flex min-h-9 items-center rounded-lg px-3 py-1.5 text-sm font-semibold text-brand-primary hover:bg-brand-muted"
              >
                {t("nav.login")}
              </Link>
              <Link
                to="/register"
                className="inline-flex min-h-9 items-center rounded-lg bg-brand-primary px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-primary-hover"
              >
                {t("nav.register")}
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

