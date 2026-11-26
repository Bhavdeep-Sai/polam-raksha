import {
  Activity,
  AlertTriangle,
  ClipboardList,
  Gavel,
  Home,
  Package,
  Search,
  Shield,
  Sprout,
  TrendingUp,
  Users,
  Volume2,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";

import type { NavItem } from "@/lib/navigation";
import { cn } from "@/lib/utils";

const NAV_ICONS = {
  home: Home,
  sprout: Sprout,
  gavel: Gavel,
  package: Package,
  clipboard: ClipboardList,
  trending: TrendingUp,
  volume: Volume2,
  search: Search,
  shield: Shield,
  users: Users,
  activity: Activity,
  alert: AlertTriangle,
};

export function NavIcon({ icon, className }: { icon: NavItem["icon"]; className?: string }) {
  const Icon = NAV_ICONS[icon];
  return <Icon className={className} aria-hidden="true" />;
}

interface SidebarProps {
  items: NavItem[];
  largeControls?: boolean;
}

export function Sidebar({ items, largeControls = false }: SidebarProps) {
  const { t } = useTranslation();

  return (
    <aside
      aria-label={t("nav.sidebarLabel")}
      className="hidden w-64 shrink-0 border-r border-brand-border bg-brand-surface p-4 md:block"
    >
      <nav className="space-y-1.5">
        {items.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path.split("/").length <= 2}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3.5 font-semibold transition-colors",
                largeControls ? "min-h-13 py-3 text-base" : "min-h-11 py-2.5 text-sm",
                isActive
                  ? "bg-brand-primary text-white"
                  : "text-brand-ink hover:bg-brand-muted",
              )
            }
          >
            <NavIcon icon={item.icon} className="h-5 w-5 shrink-0" />
            <span>{t(item.labelKey)}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

