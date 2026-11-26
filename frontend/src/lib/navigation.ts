import type { UserRole } from "@/services/api";

export interface NavItem {
  path: string;
  labelKey: string;
  icon:
    | "home"
    | "sprout"
    | "gavel"
    | "package"
    | "clipboard"
    | "trending"
    | "volume"
    | "search"
    | "shield"
    | "users"
    | "activity"
    | "alert";
  mobilePrimary?: boolean;
}

export const PUBLIC_NAV: NavItem[] = [
  { path: "/", labelKey: "nav.home", icon: "home", mobilePrimary: true },
  { path: "/login", labelKey: "nav.login", icon: "users", mobilePrimary: true },
  { path: "/register", labelKey: "nav.register", icon: "sprout", mobilePrimary: true },
  { path: "/system", labelKey: "nav.system", icon: "activity", mobilePrimary: true },
];

export const ROLE_NAV: Record<UserRole, NavItem[]> = {
  FARMER: [
    { path: "/farmer", labelKey: "nav.farmer.sell", icon: "sprout", mobilePrimary: true },
    { path: "/farmer/auctions", labelKey: "nav.farmer.auctions", icon: "gavel", mobilePrimary: true },
    { path: "/farmer/offers", labelKey: "nav.farmer.offers", icon: "package", mobilePrimary: true },
    { path: "/farmer/orders", labelKey: "nav.farmer.orders", icon: "clipboard", mobilePrimary: true },
    { path: "/farmer/prices", labelKey: "nav.farmer.prices", icon: "trending" },
    { path: "/farmer/voice", labelKey: "nav.farmer.voice", icon: "volume" },
  ],
  BUYER: [
    { path: "/buyer", labelKey: "nav.buyer.discover", icon: "search", mobilePrimary: true },
    { path: "/buyer/auctions", labelKey: "nav.buyer.auctions", icon: "gavel", mobilePrimary: true },
    { path: "/buyer/bids", labelKey: "nav.buyer.bids", icon: "trending", mobilePrimary: true },
    { path: "/buyer/commitments", labelKey: "nav.buyer.commitments", icon: "clipboard" },
    { path: "/buyer/orders", labelKey: "nav.buyer.orders", icon: "package", mobilePrimary: true },
    { path: "/buyer/reliability", labelKey: "nav.buyer.reliability", icon: "shield" },
  ],
  OPERATOR: [
    { path: "/operator", labelKey: "nav.operator.registerFarmer", icon: "users", mobilePrimary: true },
    { path: "/operator/list-produce", labelKey: "nav.operator.listProduce", icon: "sprout", mobilePrimary: true },
    { path: "/operator/history", labelKey: "nav.operator.history", icon: "clipboard", mobilePrimary: true },
  ],
  ADMIN: [
    { path: "/admin", labelKey: "nav.admin.users", icon: "users", mobilePrimary: true },
    { path: "/admin/auctions", labelKey: "nav.admin.auctions", icon: "gavel", mobilePrimary: true },
    { path: "/admin/failed-collections", labelKey: "nav.admin.failedCollections", icon: "alert" },
    { path: "/admin/recovery", labelKey: "nav.admin.recovery", icon: "activity", mobilePrimary: true },
    { path: "/admin/analytics", labelKey: "nav.admin.analytics", icon: "trending" },
    { path: "/admin/audit", labelKey: "nav.admin.audit", icon: "clipboard", mobilePrimary: true },
  ],
};

