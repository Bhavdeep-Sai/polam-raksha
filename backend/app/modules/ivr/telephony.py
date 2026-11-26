import hashlib
import hmac
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class NormalizedTelephonyEvent:
    provider: str
    external_call_id: str
    webhook_id: str
    caller_phone: str
    digits: str
    language: str = "te"


class TelephonyProviderAdapter(Protocol):
    """Provider interface for telephony channels (Browser Simulator, Asterisk/SIP, Exotel)."""

    provider_name: str

    def verify_signature(
        self, *, raw_body: bytes, signature: str | None, secret: str
    ) -> bool: ...

    def parse_inbound_event(self, payload: dict[str, Any]) -> NormalizedTelephonyEvent: ...

    def format_response(
        self, prompt_payload: dict[str, Any], session_state: str
    ) -> dict[str, Any]: ...


class BrowserSimulatorAdapter:
    provider_name = "BROWSER_SIMULATOR"

    def verify_signature(
        self, *, raw_body: bytes, signature: str | None, secret: str
    ) -> bool:
        return True

    def parse_inbound_event(self, payload: dict[str, Any]) -> NormalizedTelephonyEvent:
        return NormalizedTelephonyEvent(
            provider=self.provider_name,
            external_call_id=str(payload["call_id"]),
            webhook_id=str(payload["webhook_id"]),
            caller_phone=str(payload["caller_phone"]),
            digits=str(payload.get("digits", "")),
            language=str(payload.get("language", "te")),
        )

    def format_response(
        self, prompt_payload: dict[str, Any], session_state: str
    ) -> dict[str, Any]:
        return {"session_state": session_state, "prompt": prompt_payload}


class AsteriskSipAdapter:
    """Documented local Asterisk/ARI webhook adapter with HMAC-SHA256 verification."""

    provider_name = "ASTERISK_SIP"

    def verify_signature(
        self, *, raw_body: bytes, signature: str | None, secret: str
    ) -> bool:
        if not signature or not secret:
            return False
        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_inbound_event(self, payload: dict[str, Any]) -> NormalizedTelephonyEvent:
        return NormalizedTelephonyEvent(
            provider=self.provider_name,
            external_call_id=str(payload["channel_id"]),
            webhook_id=str(payload["event_id"]),
            caller_phone=str(payload["caller_number"]),
            digits=str(payload.get("dtmf_digit", "")),
            language=str(payload.get("language", "te")),
        )

    def format_response(
        self, prompt_payload: dict[str, Any], session_state: str
    ) -> dict[str, Any]:
        return {
            "asterisk_action": "PLAY_AND_GATHER"
            if session_state not in {"COMPLETED", "EXPIRED"}
            else "HANGUP",
            "audio_file": prompt_payload.get("audio_url"),
            "transcript": prompt_payload.get("transcript"),
        }


class ExotelAdapter:
    """Documented Exotel Passthru webhook adapter (requires Indian KYC & credits for live calls)."""

    provider_name = "EXOTEL"

    def verify_signature(
        self, *, raw_body: bytes, signature: str | None, secret: str
    ) -> bool:
        if not signature or not secret:
            return False
        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_inbound_event(self, payload: dict[str, Any]) -> NormalizedTelephonyEvent:
        return NormalizedTelephonyEvent(
            provider=self.provider_name,
            external_call_id=str(payload["CallSid"]),
            webhook_id=str(
                payload.get("EventId")
                or f"{payload['CallSid']}:{payload.get('digits', '')}"
            ),
            caller_phone=str(payload["From"]),
            digits=str(payload.get("digits", "")).strip('"'),
            language=str(payload.get("CustomField", "te")),
        )

    def format_response(
        self, prompt_payload: dict[str, Any], session_state: str
    ) -> dict[str, Any]:
        return {
            "exotel_action": "gather"
            if session_state not in {"COMPLETED", "EXPIRED"}
            else "hangup",
            "say": prompt_payload.get("transcript"),
        }


ADAPTERS: dict[str, TelephonyProviderAdapter] = {
    "BROWSER_SIMULATOR": BrowserSimulatorAdapter(),
    "ASTERISK_SIP": AsteriskSipAdapter(),
    "EXOTEL": ExotelAdapter(),
}
