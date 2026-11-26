import re
from dataclasses import dataclass
from typing import Literal

UrgencyLiteral = Literal["WITHIN_2H", "WITHIN_6H", "WITHIN_12H", "WITHIN_24H"]


@dataclass(frozen=True)
class VoiceExtractionResult:
    available: bool
    transcript: str
    crop_code: str | None
    quantity_kg: float | None
    price_inr_per_kg: int | None
    urgency_option: UrgencyLiteral | None
    reason: str | None = None


_CROP_KEYWORDS: dict[str, str] = {
    "tomato": "TOMATO",
    "టమాటా": "TOMATO",
    "onion": "ONION",
    "ఉల్లిపాయ": "ONION",
    "brinjal": "BRINJAL",
    "వంకాయ": "BRINJAL",
    "okra": "OKRA",
    "బెండకాయ": "OKRA",
    "mango": "MANGO",
    "మామిడి": "MANGO",
}


def extract_listing_fields_from_transcript(transcript: str) -> VoiceExtractionResult:
    """Deterministically extract structured listing fields from a transcript for read-back."""
    lower = transcript.lower()
    crop_code: str | None = None
    for kw, code in _CROP_KEYWORDS.items():
        if kw in lower or kw in transcript:
            crop_code = code
            break

    qty_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|kilo|kilogram|కిలో|కిలోలు)", lower)
    quantity_kg = float(qty_match.group(1)) if qty_match else None

    price_match = re.search(
        r"(?:rs\.?|rupees|inr|₹)\s*(\d+)|(\d+)\s*(?:rupees|rs\.?|inr|రూపాయలు)",
        lower,
    )
    price_inr: int | None = None
    if price_match:
        raw_price = price_match.group(1) or price_match.group(2)
        if raw_price:
            price_inr = int(raw_price)

    urgency: UrgencyLiteral | None = None
    if "2 hour" in lower or "2 గంట" in transcript:
        urgency = "WITHIN_2H"
    elif "6 hour" in lower or "6 గంట" in transcript:
        urgency = "WITHIN_6H"
    elif "12 hour" in lower or "12 గంట" in transcript:
        urgency = "WITHIN_12H"
    elif "24 hour" in lower or "24 గంట" in transcript:
        urgency = "WITHIN_24H"

    return VoiceExtractionResult(
        available=True,
        transcript=transcript,
        crop_code=crop_code,
        quantity_kg=quantity_kg,
        price_inr_per_kg=price_inr,
        urgency_option=urgency,
    )


def transcribe_audio_with_optional_whisper(audio_path: str) -> VoiceExtractionResult:
    """Optional Faster Whisper adapter; degrades gracefully when not installed."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return VoiceExtractionResult(
            available=False,
            transcript="",
            crop_code=None,
            quantity_kg=None,
            price_inr_per_kg=None,
            urgency_option=None,
            reason="Optional faster-whisper speech dependency is not installed.",
        )

    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, language="te")
    text = " ".join(seg.text for seg in segments).strip()
    return extract_listing_fields_from_transcript(text)
