export function formatCurrencyPaise(paise: number, locale = "en-IN"): string {
  const rupees = paise / 100;
  return new Intl.NumberFormat(locale === "te" ? "te-IN" : "en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: paise % 100 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(rupees);
}

export function formatQuantityGrams(grams: number, locale = "en"): string {
  const isTelugu = locale.startsWith("te");
  if (grams < 1000) {
    return `${grams} ${isTelugu ? "గ్రా" : "g"}`;
  }
  const kg = grams / 1000;
  const formatted = Number.isInteger(kg) ? kg.toString() : kg.toFixed(2).replace(/\.?0+$/, "");
  return `${formatted} ${isTelugu ? "కిలో" : "kg"}`;
}

export function formatIstDateTime(utcIso: string, locale = "en"): string {
  const date = new Date(utcIso);
  if (Number.isNaN(date.getTime())) {
    return utcIso;
  }
  return new Intl.DateTimeFormat(locale.startsWith("te") ? "te-IN" : "en-IN", {
    timeZone: "Asia/Kolkata",
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export interface CountdownResult {
  hours: number;
  minutes: number;
  isUrgent: boolean;
  isExpired: boolean;
}

export function computeCountdown(targetUtcIso: string, nowMs = Date.now()): CountdownResult {
  const targetMs = new Date(targetUtcIso).getTime();
  if (Number.isNaN(targetMs) || targetMs <= nowMs) {
    return { hours: 0, minutes: 0, isUrgent: true, isExpired: true };
  }
  const diffMinutes = Math.floor((targetMs - nowMs) / 60_000);
  const hours = Math.floor(diffMinutes / 60);
  const minutes = diffMinutes % 60;
  return {
    hours,
    minutes,
    isUrgent: hours < 6,
    isExpired: false,
  };
}

