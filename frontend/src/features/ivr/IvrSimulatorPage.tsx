import { PhoneCall, PhoneOff, VolumeX } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { AccessibleFormField } from "@/components/common/AccessibleFormField";
import { ErrorState } from "@/components/common/ErrorState";
import { PageHeader } from "@/components/common/PageHeader";
import { VoicePrompt } from "@/components/common/VoicePrompt";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient, ApiError, type IvrSessionResponse } from "@/services/api";

const KEYPAD_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"];

export function IvrSimulatorPage() {
  const { t, i18n } = useTranslation();
  const [phone, setPhone] = useState("+919000000001");
  const [digitBuffer, setDigitBuffer] = useState("");
  const [session, setSession] = useState<IvrSessionResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const startCall = async () => {
    setErrorMsg(null);
    setBusy(true);
    try {
      const res = await apiClient.startIvrSession({
        caller_phone: phone,
        language: i18n.language.startsWith("te") ? "te" : "en",
        provider: "BROWSER_SIMULATOR",
        external_call_id: `browser-${phone}`,
      });
      setSession(res);
      setDigitBuffer("");
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : t("common.errorTitle"));
    } finally {
      setBusy(false);
    }
  };

  const sendDigits = async (digits: string) => {
    if (!session || !digits) return;
    setErrorMsg(null);
    setBusy(true);
    try {
      const webhookId =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `wh-${Date.now()}`;
      const res = await apiClient.sendIvrDtmf(session.session_id, {
        digits,
        webhook_id: webhookId,
      });
      setSession(res);
      setDigitBuffer("");
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : t("common.errorTitle"));
    } finally {
      setBusy(false);
    }
  };

  const handleKeyPress = (key: string) => {
    if (!session) return;
    const isNumericEntry =
      session.session_state === "AUTH_PIN" ||
      session.session_state === "SELL_ENTER_QUANTITY" ||
      session.session_state === "SELL_ENTER_PRICE";

    if (isNumericEntry) {
      if (key === "#") {
        void sendDigits(`${digitBuffer}#`);
      } else if (key === "*") {
        setDigitBuffer("");
        void sendDigits("*");
      } else {
        setDigitBuffer((prev) => `${prev}${key}`);
      }
      return;
    }

    void sendDigits(key);
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader
        title="IVR & Keypad Phone Simulator"
        description={t("landing.accessibilityBody")}
      />

      {errorMsg ? <ErrorState message={errorMsg} /> : null}

      <Card className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-52 flex-1">
            <AccessibleFormField id="ivr-phone" label={t("auth.phoneLabel")}>
              <Input
                id="ivr-phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </AccessibleFormField>
          </div>
          <Button onClick={() => void startCall()} disabled={busy}>
            <PhoneCall className="h-4 w-4" aria-hidden="true" />
            {session ? "Resume / New Call" : "Start IVR Call"}
          </Button>
          {session ? (
            <Button variant="outline" onClick={() => setSession(null)}>
              <PhoneOff className="h-4 w-4" aria-hidden="true" />
              Hang Up
            </Button>
          ) : null}
        </div>
      </Card>

      {session ? (
        <Card className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-brand-border pb-3">
            <span className="text-sm font-bold text-brand-primary">
              State: {session.session_state}
            </span>
            <VoicePrompt text={session.prompt.transcript} />
          </div>

          <div className="space-y-2 rounded-lg border border-brand-border bg-brand-bg p-4">
            <p className="text-base font-semibold text-brand-ink">
              {session.prompt.transcript}
            </p>
            {!session.prompt.audio_available ? (
              <p className="flex items-center gap-1.5 text-xs text-brand-ink-muted">
                <VolumeX className="h-3.5 w-3.5" aria-hidden="true" />
                <span>
                  Local WAV audio pack ({session.prompt.audio_url}) not bundled in MVP; using
                  transcript + browser SpeechSynthesis where supported.
                </span>
              </p>
            ) : null}
          </div>

          {digitBuffer ? (
            <div className="rounded-lg border border-brand-primary/30 bg-brand-muted px-4 py-2 text-center font-mono text-lg font-bold">
              {digitBuffer}
            </div>
          ) : null}

          <div className="mx-auto grid max-w-xs grid-cols-3 gap-3">
            {KEYPAD_KEYS.map((key) => (
              <Button
                key={key}
                variant="outline"
                size="lg"
                disabled={busy}
                onClick={() => handleKeyPress(key)}
                className="min-h-14 text-xl font-bold"
              >
                {key}
              </Button>
            ))}
          </div>
        </Card>
      ) : null}
    </div>
  );
}

