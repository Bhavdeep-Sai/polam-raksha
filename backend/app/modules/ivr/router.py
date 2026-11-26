import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.modules.ivr.prompts import PROMPT_CATALOG
from app.modules.ivr.state_machine import process_dtmf_step, start_or_resume_session
from app.modules.ivr.telephony import ADAPTERS
from app.modules.ivr.voice_adapter import extract_listing_fields_from_transcript

router = APIRouter(prefix="/ivr", tags=["ivr"])


class StartIvrSessionRequest(BaseModel):
    caller_phone: str = Field(min_length=10, max_length=20)
    language: Literal["te", "en"] = "te"
    provider: Literal["BROWSER_SIMULATOR", "ASTERISK_SIP", "EXOTEL"] = "BROWSER_SIMULATOR"
    external_call_id: str | None = Field(default=None, max_length=128)


class DtmfInputRequest(BaseModel):
    digits: str = Field(min_length=1, max_length=32)
    webhook_id: str | None = Field(default=None, max_length=128)


class IvrPromptResponse(BaseModel):
    prompt_key: str
    language: str
    audio_url: str
    audio_available: bool
    transcript: str
    number_audio_tokens: list[str]


class IvrSessionResponse(BaseModel):
    session_id: uuid.UUID
    session_state: str
    language: str
    caller_phone: str
    retry_count: int
    draft: dict[str, Any]
    prompt: IvrPromptResponse


class VoiceExtractRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=1000)


class VoiceExtractResponse(BaseModel):
    available: bool
    transcript: str
    crop_code: str | None
    quantity_kg: float | None
    price_inr_per_kg: int | None
    urgency_option: str | None
    reason: str | None = None


@router.get("/prompts", summary="Get centralized Telugu/English IVR audio prompt catalog")
def get_prompt_catalog() -> list[dict[str, str]]:
    return [
        {
            "key": spec.key,
            "te_transcript": spec.te_transcript,
            "en_transcript": spec.en_transcript,
            "audio_filename": spec.audio_filename,
        }
        for spec in PROMPT_CATALOG.values()
    ]


@router.post(
    "/sessions",
    response_model=IvrSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start or resume an IVR session",
)
def start_session(
    payload: StartIvrSessionRequest,
    db: Annotated[Session, Depends(get_db)],
) -> IvrSessionResponse:
    session, prompt = start_or_resume_session(
        db,
        caller_phone=payload.caller_phone,
        language=payload.language,
        provider=payload.provider,
        external_call_id=payload.external_call_id,
    )
    return IvrSessionResponse(
        session_id=session.id,
        session_state=session.session_state,
        language=session.language,
        caller_phone=session.caller_phone,
        retry_count=session.retry_count,
        draft=dict(session.draft_json),
        prompt=IvrPromptResponse(**prompt),
    )


@router.post(
    "/sessions/{session_id}/dtmf",
    response_model=IvrSessionResponse,
    summary="Process keypad DTMF input through the IVR state machine",
)
def send_dtmf(
    session_id: uuid.UUID,
    payload: DtmfInputRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> IvrSessionResponse:
    ip = request.client.host if request.client else None
    session, prompt = process_dtmf_step(
        db,
        session_id=session_id,
        raw_digits=payload.digits,
        settings=settings,
        webhook_id=payload.webhook_id,
        ip_address=ip,
    )
    return IvrSessionResponse(
        session_id=session.id,
        session_state=session.session_state,
        language=session.language,
        caller_phone=session.caller_phone,
        retry_count=session.retry_count,
        draft=dict(session.draft_json),
        prompt=IvrPromptResponse(**prompt),
    )


@router.post(
    "/webhooks/{provider}",
    summary="Authenticated telephony provider webhook (Asterisk/SIP or Exotel)",
)
async def provider_webhook(
    provider: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_provider_signature: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    adapter = ADAPTERS.get(provider.upper())
    if adapter is None:
        raise AppError(
            code="unsupported_telephony_provider",
            message=f"Unsupported telephony provider: {provider}",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    raw_body = await request.body()
    if not adapter.verify_signature(
        raw_body=raw_body,
        signature=x_provider_signature,
        secret=settings.ivr_webhook_secret,
    ):
        raise AppError(
            code="invalid_webhook_signature",
            message="Provider webhook signature verification failed",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    payload = await request.json()
    event = adapter.parse_inbound_event(payload)
    session, prompt = start_or_resume_session(
        db,
        caller_phone=event.caller_phone,
        language=event.language,
        provider=event.provider,
        external_call_id=event.external_call_id,
    )
    if event.digits:
        session, prompt = process_dtmf_step(
            db,
            session_id=session.id,
            raw_digits=event.digits,
            settings=settings,
            webhook_id=event.webhook_id,
            ip_address=request.client.host if request.client else None,
        )
    return adapter.format_response(prompt, session.session_state)


@router.post(
    "/voice/extract",
    response_model=VoiceExtractResponse,
    summary="Extract structured listing fields from voice transcript for read-back",
)
def extract_voice_fields(payload: VoiceExtractRequest) -> VoiceExtractResponse:
    res = extract_listing_fields_from_transcript(payload.transcript)
    return VoiceExtractResponse(
        available=res.available,
        transcript=res.transcript,
        crop_code=res.crop_code,
        quantity_kg=res.quantity_kg,
        price_inr_per_kg=res.price_inr_per_kg,
        urgency_option=res.urgency_option,
        reason=res.reason,
    )

