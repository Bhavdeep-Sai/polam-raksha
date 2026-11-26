import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.modules.allocation.models import Allocation, AllocationRun, AllocationRunStatus
from app.modules.allocation.service import approve_allocation_run
from app.modules.auctions.models import Auction
from app.modules.auth.service import authenticate_pin, record_audit_event
from app.modules.ivr.input_parser import parse_dtmf_digits
from app.modules.ivr.models import IvrSession
from app.modules.ivr.prompts import build_prompt_payload
from app.modules.listings.deadline_policy import UrgencyOption, compute_deadline_schedule
from app.modules.listings.models import CropCatalog, ListingStatus, ProduceListing
from app.modules.listings.schemas import CreateListingRequest, UpdateListingRequest
from app.modules.listings.service import (
    cancel_uncommitted_inventory,
    create_produce_listing,
    list_active_crops,
    update_produce_listing,
)
from app.modules.users.models import FarmerProfile, User
from app.shared.time import IST_TIMEZONE, utc_now

MAX_RETRIES = 3
SESSION_TTL_MINUTES = 15

URGENCY_KEYPAD_MAP: dict[int, UrgencyOption] = {
    1: "WITHIN_2H",
    2: "WITHIN_6H",
    3: "WITHIN_12H",
    4: "WITHIN_24H",
}


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _format_ist_short(dt: datetime) -> str:
    return _ensure_utc(dt).astimezone(IST_TIMEZONE).strftime("%d %b %I:%M %p IST")


def _prompt_for_state(
    db: Session, session: IvrSession
) -> dict[str, Any]:
    state = session.session_state
    lang = session.language
    draft = dict(session.draft_json)

    if state == "SELL_SELECT_CROP":
        crops = list_active_crops(db)
        options_str = ", ".join(
            f"{idx + 1} {c.name_te if lang.startswith('te') else c.name_en}"
            for idx, c in enumerate(crops[:9])
        )
        return build_prompt_payload(
            prompt_key="SELL_SELECT_CROP",
            language=lang,
            params={"crop_options": options_str},
        )

    if state == "SELL_CONFIRM":
        return build_prompt_payload(
            prompt_key="SELL_CONFIRM",
            language=lang,
            params={
                "crop_name": draft.get("crop_name", ""),
                "quantity_kg": draft.get("quantity_kg", 0),
                "price_inr": draft.get("price_inr", 0),
                "deadline_ist": draft.get("deadline_ist", ""),
            },
            dynamic_numbers=[
                int(draft.get("quantity_kg", 0)),
                int(draft.get("price_inr", 0)),
            ],
        )

    if state == "OFFER_APPROVAL":
        return build_prompt_payload(
            prompt_key="OFFER_APPROVAL",
            language=lang,
            params={
                "crop_name": draft.get("offer_crop_name", ""),
                "qty_kg": draft.get("offer_qty_kg", 0),
                "gross_inr": draft.get("offer_gross_inr", 0),
                "transport_inr": draft.get("offer_transport_inr", 0),
                "net_inr": draft.get("offer_net_inr", 0),
                "deadline_ist": draft.get("offer_deadline_ist", ""),
            },
            dynamic_numbers=[
                int(draft.get("offer_qty_kg", 0)),
                int(draft.get("offer_net_inr", 0)),
            ],
        )

    return build_prompt_payload(prompt_key=state, language=lang)


def start_or_resume_session(
    db: Session,
    *,
    caller_phone: str,
    language: str = "te",
    provider: str = "BROWSER_SIMULATOR",
    external_call_id: str | None = None,
    authenticated_user: User | None = None,
) -> tuple[IvrSession, dict[str, Any]]:
    """Start a new IVR session or resume an interrupted non-expired session."""
    now = utc_now()
    if external_call_id:
        existing = db.scalar(
            select(IvrSession).where(
                IvrSession.external_call_id == external_call_id,
                IvrSession.ended_at.is_(None),
            )
        )
        if existing is not None:
            if existing.expires_at and _ensure_utc(existing.expires_at) > now:
                existing.last_activity_at = now
                db.commit()
                return existing, _prompt_for_state(db, existing)

    initial_state = "MAIN_MENU" if authenticated_user is not None else "AUTH_PIN"
    session = IvrSession(
        user_id=authenticated_user.id if authenticated_user else None,
        caller_phone=caller_phone,
        provider=provider,
        external_call_id=external_call_id,
        session_state=initial_state,
        language=language,
        retry_count=0,
        draft_json={},
        started_at=now,
        last_activity_at=now,
        expires_at=now + timedelta(minutes=SESSION_TTL_MINUTES),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, _prompt_for_state(db, session)


def process_dtmf_step(
    db: Session,
    *,
    session_id: uuid.UUID,
    raw_digits: str,
    settings: Settings,
    webhook_id: str | None = None,
    ip_address: str | None = None,
) -> tuple[IvrSession, dict[str, Any]]:
    """Advance the IVR state machine by one keypad input, delegating to core services."""
    session = db.scalar(select(IvrSession).where(IvrSession.id == session_id).with_for_update())
    if session is None:
        raise AppError(
            code="ivr_session_not_found",
            message="IVR session not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Webhook replay / duplicate delivery protection
    if webhook_id and session.last_webhook_id == webhook_id:
        return session, _prompt_for_state(db, session)

    now = utc_now()
    if session.expires_at and _ensure_utc(session.expires_at) <= now:
        session.session_state = "EXPIRED"
        session.ended_at = now
        db.commit()
        return session, build_prompt_payload(
            prompt_key="SESSION_EXPIRED", language=session.language
        )

    parsed = parse_dtmf_digits(raw_digits)
    draft = dict(session.draft_json)
    state = session.session_state
    lang = session.language

    if webhook_id:
        session.last_webhook_id = webhook_id
    session.last_activity_at = now
    session.expires_at = now + timedelta(minutes=SESSION_TTL_MINUTES)

    def _invalid_retry(current_prompt: dict[str, Any]) -> tuple[IvrSession, dict[str, Any]]:
        session.retry_count += 1
        if session.retry_count >= MAX_RETRIES:
            session.session_state = "HELP"
            session.ended_at = now
            db.commit()
            return session, build_prompt_payload(prompt_key="HELP", language=lang)
        session.draft_json = draft
        db.commit()
        inv = build_prompt_payload(prompt_key="INVALID_INPUT", language=lang)
        inv["transcript"] = f"{inv['transcript']} {current_prompt['transcript']}"
        return session, inv

    if state == "AUTH_PIN":
        if not parsed.normalized.isdigit() or len(parsed.normalized) < 4:
            return _invalid_retry(_prompt_for_state(db, session))
        token_res, _ = authenticate_pin(
            db,
            phone_number=session.caller_phone,
            pin=parsed.normalized,
            settings=settings,
            ip_address=ip_address,
        )
        session.user_id = token_res.user.id
        session.session_state = "MAIN_MENU"
        session.retry_count = 0
        db.commit()
        return session, _prompt_for_state(db, session)

    user = db.scalar(select(User).where(User.id == session.user_id))
    if user is None:
        raise AppError(
            code="ivr_unauthenticated",
            message="IVR session is not authenticated",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if state == "MAIN_MENU":
        if parsed.is_repeat_or_back:
            db.commit()
            return session, _prompt_for_state(db, session)
        if parsed.is_help:
            db.commit()
            return session, build_prompt_payload(prompt_key="HELP", language=lang)
        if parsed.numeric_value == 1:
            session.session_state = "SELL_SELECT_CROP"
            session.retry_count = 0
            db.commit()
            return session, _prompt_for_state(db, session)
        if parsed.numeric_value == 2:
            latest = db.scalar(
                select(ProduceListing)
                .where(ProduceListing.farmer_id == user.id)
                .order_by(ProduceListing.created_at.desc())
            )
            summary = (
                f"{latest.status.value}, {latest.available_quantity_grams // 1000} kg"
                if latest
                else "No active listings"
            )
            db.commit()
            return session, build_prompt_payload(
                prompt_key="AUCTION_STATUS",
                language=lang,
                params={"summary": summary},
            )
        if parsed.numeric_value == 3:
            pending_run = db.scalar(
                select(AllocationRun)
                .join(Auction, Auction.id == AllocationRun.auction_id)
                .join(ProduceListing, ProduceListing.id == Auction.listing_id)
                .where(
                    ProduceListing.farmer_id == user.id,
                    AllocationRun.status == AllocationRunStatus.SOLVED,
                    AllocationRun.is_approved.is_(False),
                )
                .order_by(AllocationRun.created_at.desc())
            )
            if pending_run is None:
                db.commit()
                return session, build_prompt_payload(
                    prompt_key="NO_PENDING_OFFER", language=lang
                )
            allocs = db.scalars(
                select(Allocation).where(Allocation.allocation_run_id == pending_run.id)
            ).all()
            total_qty_kg = sum(a.allocated_quantity_grams for a in allocs) // 1000
            auction = db.scalar(select(Auction).where(Auction.id == pending_run.auction_id))
            listing = (
                db.scalar(select(ProduceListing).where(ProduceListing.id == auction.listing_id))
                if auction
                else None
            )
            crop = (
                db.scalar(select(CropCatalog).where(CropCatalog.id == listing.crop_id))
                if listing
                else None
            )
            draft["pending_run_id"] = str(pending_run.id)
            draft["offer_crop_name"] = (
                (crop.name_te if lang.startswith("te") else crop.name_en) if crop else "Crop"
            )
            draft["offer_qty_kg"] = total_qty_kg
            draft["offer_gross_inr"] = pending_run.gross_revenue_paise // 100
            draft["offer_transport_inr"] = pending_run.transportation_cost_paise // 100
            draft["offer_net_inr"] = pending_run.estimated_net_revenue_paise // 100
            draft["offer_deadline_ist"] = (
                _format_ist_short(listing.spoilage_deadline_at) if listing else ""
            )
            session.draft_json = draft
            session.session_state = "OFFER_APPROVAL"
            db.commit()
            return session, _prompt_for_state(db, session)
        if parsed.numeric_value == 4:
            latest = db.scalar(
                select(ProduceListing)
                .where(
                    ProduceListing.farmer_id == user.id,
                    ProduceListing.status == ListingStatus.ACTIVE,
                )
                .order_by(ProduceListing.created_at.desc())
            )
            if latest:
                update_produce_listing(
                    db,
                    listing_id=latest.id,
                    payload=UpdateListingRequest(
                        floor_price_paise_per_kg=latest.floor_price_paise_per_kg
                    ),
                    current_user=user,
                    ip_address=ip_address,
                )
            return session, _prompt_for_state(db, session)
        if parsed.numeric_value == 5:
            latest = db.scalar(
                select(ProduceListing)
                .where(
                    ProduceListing.farmer_id == user.id,
                    ProduceListing.status == ListingStatus.ACTIVE,
                )
                .order_by(ProduceListing.created_at.desc())
            )
            if latest:
                cancel_uncommitted_inventory(
                    db,
                    listing_id=latest.id,
                    current_user=user,
                    ip_address=ip_address,
                )
            return session, _prompt_for_state(db, session)
        return _invalid_retry(_prompt_for_state(db, session))

    if state == "SELL_SELECT_CROP":
        if parsed.is_repeat_or_back:
            db.commit()
            return session, _prompt_for_state(db, session)
        crops = list_active_crops(db)
        if (
            parsed.numeric_value is None
            or parsed.numeric_value < 1
            or parsed.numeric_value > len(crops)
        ):
            return _invalid_retry(_prompt_for_state(db, session))
        chosen = crops[parsed.numeric_value - 1]
        draft["crop_id"] = str(chosen.id)
        draft["crop_name"] = chosen.name_te if lang.startswith("te") else chosen.name_en
        session.draft_json = draft
        session.session_state = "SELL_ENTER_QUANTITY"
        session.retry_count = 0
        db.commit()
        return session, _prompt_for_state(db, session)

    if state == "SELL_ENTER_QUANTITY":
        if parsed.is_repeat_or_back:
            session.session_state = "SELL_SELECT_CROP"
            db.commit()
            return session, _prompt_for_state(db, session)
        if parsed.numeric_value is None or parsed.numeric_value <= 0:
            return _invalid_retry(_prompt_for_state(db, session))
        draft["quantity_kg"] = parsed.numeric_value
        session.draft_json = draft
        session.session_state = "SELL_ENTER_PRICE"
        session.retry_count = 0
        db.commit()
        return session, _prompt_for_state(db, session)

    if state == "SELL_ENTER_PRICE":
        if parsed.is_repeat_or_back:
            session.session_state = "SELL_ENTER_QUANTITY"
            db.commit()
            return session, _prompt_for_state(db, session)
        if parsed.numeric_value is None or parsed.numeric_value <= 0:
            return _invalid_retry(_prompt_for_state(db, session))
        draft["price_inr"] = parsed.numeric_value
        session.draft_json = draft
        session.session_state = "SELL_SELECT_URGENCY"
        session.retry_count = 0
        db.commit()
        return session, _prompt_for_state(db, session)

    if state == "SELL_SELECT_URGENCY":
        if parsed.is_repeat_or_back:
            session.session_state = "SELL_ENTER_PRICE"
            db.commit()
            return session, _prompt_for_state(db, session)
        if parsed.numeric_value not in URGENCY_KEYPAD_MAP:
            return _invalid_retry(_prompt_for_state(db, session))
        urgency = URGENCY_KEYPAD_MAP[parsed.numeric_value]
        schedule = compute_deadline_schedule(now=now, urgency_option=urgency)
        draft["urgency_option"] = urgency
        draft["deadline_ist"] = _format_ist_short(schedule.collection_deadline_at)
        session.draft_json = draft
        session.session_state = "SELL_CONFIRM"
        session.retry_count = 0
        db.commit()
        return session, _prompt_for_state(db, session)

    if state == "SELL_CONFIRM":
        if parsed.is_repeat_or_back or parsed.numeric_value == 2:
            session.session_state = "SELL_ENTER_QUANTITY"
            db.commit()
            return session, _prompt_for_state(db, session)
        if parsed.is_help:
            session.session_state = "MAIN_MENU"
            db.commit()
            return session, _prompt_for_state(db, session)
        if parsed.numeric_value != 1:
            return _invalid_retry(_prompt_for_state(db, session))

        # Idempotent listing creation via existing listing service
        if draft.get("created_listing_id"):
            short_id = str(draft["created_listing_id"])[:8]
            return session, build_prompt_payload(
                prompt_key="SELL_CREATED", language=lang, params={"short_id": short_id}
            )

        profile = db.scalar(select(FarmerProfile).where(FarmerProfile.user_id == user.id))
        approx_loc = f"{profile.village}, {profile.district}" if profile else "Local Village"
        pickup_addr = profile.exact_pickup_address if profile else "Village Collection Point"

        listing_res = create_produce_listing(
            db,
            payload=CreateListingRequest(
                farmer_id=user.id,
                crop_id=uuid.UUID(str(draft["crop_id"])),
                quantity_value=float(draft["quantity_kg"]),
                quantity_unit="KG",
                floor_price_paise_per_kg=int(draft["price_inr"]) * 100,
                harvested_at=now - timedelta(hours=1),
                urgency_option=draft["urgency_option"],
                approx_location_label=approx_loc,
                exact_pickup_address=pickup_addr,
                consent_confirmed=True,
            ),
            current_user=user,
            ip_address=ip_address,
        )
        draft["created_listing_id"] = str(listing_res.id)
        session.draft_json = draft
        session.session_state = "MAIN_MENU"
        db.commit()
        return session, build_prompt_payload(
            prompt_key="SELL_CREATED",
            language=lang,
            params={"short_id": str(listing_res.id)[:8]},
        )

    if state == "OFFER_APPROVAL":
        if parsed.is_repeat_or_back:
            db.commit()
            return session, _prompt_for_state(db, session)
        if parsed.is_help:
            db.commit()
            return session, build_prompt_payload(prompt_key="HELP", language=lang)
        run_id_str = draft.get("pending_run_id")
        if parsed.numeric_value == 1 and run_id_str:
            approve_allocation_run(
                db,
                run_id=uuid.UUID(str(run_id_str)),
                current_user=user,
                ip_address=ip_address,
            )
            session.session_state = "MAIN_MENU"
            db.commit()
            return session, build_prompt_payload(prompt_key="OFFER_APPROVED", language=lang)
        if parsed.numeric_value == 2:
            record_audit_event(
                db,
                actor_user_id=user.id,
                action="IVR_OFFER_REJECTED",
                resource_type="allocation_run",
                resource_id=str(run_id_str) if run_id_str else None,
                ip_address=ip_address,
            )
            session.session_state = "MAIN_MENU"
            db.commit()
            return session, _prompt_for_state(db, session)
        return _invalid_retry(_prompt_for_state(db, session))

    session.session_state = "MAIN_MENU"
    db.commit()
    return session, _prompt_for_state(db, session)
