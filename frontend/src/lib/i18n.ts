import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import { env } from "@/lib/env";
import enCommon from "@/locales/en/common.json";
import teCommon from "@/locales/te/common.json";

void i18n.use(initReactI18next).init({
  resources: {
    en: { common: enCommon },
    te: { common: teCommon },
  },
  lng: env.VITE_DEFAULT_LOCALE,
  fallbackLng: "en",
  defaultNS: "common",
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;

