import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";

import { NavIcon } from "@/components/layout/Sidebar";
import type { NavItem } from "@/lib/navigation";
import { cn } from "@/lib/utils";

interface MobileNavigationProps {
  items: NavItem[];
}

export function MobileNavigation({ items }: MobileNavigationProps) {
  const { t } = useTranslation();
  const primaryItems = items.filter((item) => item.mobilePrimary).slice(0, 4);

  if (primaryItems.length === 0) return null;

  return (
    <nav
      aria-label={t("nav.mobileLabel")}
      className="fixed inset-x-0 bottom-0 z-30 border-t border-brand-border bg-brand-surface md:hidden"
    >
      <div className="grid grid-cols-4">
        {primaryItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path.split("/").length <= 2}
            className={({ isActive }) =>
              cn(
                "flex min-h-14 flex-col items-center justify-center gap-1 px-1 py-2 text-center text-xs font-semibold",
                isActive
                  ? "bg-brand-muted text-brand-primary"
                  : "text-brand-ink-muted hover:bg-brand-bg",
              )
            }
          >
            <NavIcon icon={item.icon} className="h-5 w-5 shrink-0" />
            <span className="max-w-full truncate">{t(item.labelKey)}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

