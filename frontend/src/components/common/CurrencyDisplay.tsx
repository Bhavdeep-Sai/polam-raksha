import { useTranslation } from "react-i18next";

import { formatCurrencyPaise } from "@/lib/format";

interface CurrencyDisplayProps {
  paise: number;
  suffix?: string;
  className?: string;
}

export function CurrencyDisplay({ paise, suffix, className }: CurrencyDisplayProps) {
  const { i18n } = useTranslation();
  const formatted = formatCurrencyPaise(paise, i18n.language);

  return (
    <span className={className}>
      {formatted}
      {suffix ? ` ${suffix}` : ""}
    </span>
  );
}

