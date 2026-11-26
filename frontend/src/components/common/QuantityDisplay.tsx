import { useTranslation } from "react-i18next";

import { formatQuantityGrams } from "@/lib/format";

interface QuantityDisplayProps {
  grams: number;
  className?: string;
}

export function QuantityDisplay({ grams, className }: QuantityDisplayProps) {
  const { i18n } = useTranslation();
  return <span className={className}>{formatQuantityGrams(grams, i18n.language)}</span>;
}

