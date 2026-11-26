import { Languages } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();
  const currentLang = i18n.language.startsWith("te") ? "te" : "en";

  const toggleLanguage = () => {
    void i18n.changeLanguage(currentLang === "te" ? "en" : "te");
  };

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={toggleLanguage}
      aria-label={`${t("languageLabel")}: ${
        currentLang === "te" ? t("switchToEnglish") : t("switchToTelugu")
      }`}
    >
      <Languages className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{currentLang === "te" ? t("switchToEnglish") : t("switchToTelugu")}</span>
    </Button>
  );
}

