import { Volume2, VolumeX } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";

interface VoicePromptProps {
  text: string;
  label?: string;
}

export function VoicePrompt({ text, label }: VoicePromptProps) {
  const { t, i18n } = useTranslation();
  const [speaking, setSpeaking] = useState(false);

  const isSupported =
    typeof window !== "undefined" && "speechSynthesis" in window;

  const handleToggle = () => {
    if (!isSupported) return;
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = i18n.language.startsWith("te") ? "te-IN" : "en-IN";
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  if (!isSupported) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-ink-muted">
        <VolumeX className="h-4 w-4" aria-hidden="true" />
        <span>{t("common.voiceUnavailable")}</span>
      </span>
    );
  }

  return (
    <Button variant="outline" size="sm" onClick={handleToggle}>
      {speaking ? (
        <VolumeX className="h-4 w-4" aria-hidden="true" />
      ) : (
        <Volume2 className="h-4 w-4" aria-hidden="true" />
      )}
      <span>{label ?? (speaking ? t("common.stopVoice") : t("common.listenVoice"))}</span>
    </Button>
  );
}

