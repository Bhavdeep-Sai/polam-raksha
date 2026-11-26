export type StatusTone = "success" | "warning" | "danger" | "neutral" | "info";

export interface StatusMeta {
  tone: StatusTone;
  labelKey: string;
  icon: "check" | "clock" | "alert" | "info" | "x";
}

export const STATUS_TONE_CLASSES: Record<StatusTone, string> = {
  success: "border-green-800/30 bg-green-100 text-green-950",
  warning: "border-amber-800/30 bg-amber-100 text-amber-950",
  danger: "border-red-800/30 bg-red-100 text-red-950",
  info: "border-sky-800/30 bg-sky-100 text-sky-950",
  neutral: "border-stone-400/50 bg-stone-200 text-stone-900",
};

export const STATUS_REGISTRY: Record<string, StatusMeta> = {
  ACTIVE: { tone: "success", labelKey: "status.ACTIVE", icon: "check" },
  OPEN: { tone: "success", labelKey: "status.OPEN", icon: "check" },
  READY: { tone: "success", labelKey: "status.READY", icon: "check" },
  CONNECTED: { tone: "success", labelKey: "status.CONNECTED", icon: "check" },
  CONFIRMED: { tone: "success", labelKey: "status.CONFIRMED", icon: "check" },
  COLLECTED: { tone: "success", labelKey: "status.COLLECTED", icon: "check" },
  RECOVERED: { tone: "info", labelKey: "status.RECOVERED", icon: "info" },
  SCHEDULED: { tone: "info", labelKey: "status.SCHEDULED", icon: "clock" },
  PENDING_CONFIRMATION: { tone: "warning", labelKey: "status.PENDING_CONFIRMATION", icon: "clock" },
  CLOSING: { tone: "warning", labelKey: "status.CLOSING", icon: "clock" },
  ALLOCATED: { tone: "info", labelKey: "status.ALLOCATED", icon: "info" },
  IN_TRANSIT: { tone: "info", labelKey: "status.IN_TRANSIT", icon: "clock" },
  DRAFT: { tone: "neutral", labelKey: "status.DRAFT", icon: "info" },
  CLOSED: { tone: "neutral", labelKey: "status.CLOSED", icon: "x" },
  COMPLETED: { tone: "success", labelKey: "status.COMPLETED", icon: "check" },
  EXPIRED: { tone: "danger", labelKey: "status.EXPIRED", icon: "alert" },
  CANCELLED: { tone: "danger", labelKey: "status.CANCELLED", icon: "x" },
  CANCELLED_BY_BUYER: { tone: "danger", labelKey: "status.CANCELLED_BY_BUYER", icon: "alert" },
  UNAVAILABLE: { tone: "danger", labelKey: "status.UNAVAILABLE", icon: "alert" },
};

export function getStatusMeta(status: string): StatusMeta {
  return (
    STATUS_REGISTRY[status.toUpperCase()] ?? {
      tone: "neutral",
      labelKey: status,
      icon: "info",
    }
  );
}

