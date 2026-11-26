from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AudioPromptSpec:
    key: str
    te_transcript: str
    en_transcript: str
    audio_filename: str


PROMPT_CATALOG: dict[str, AudioPromptSpec] = {
    "AUTH_PIN": AudioPromptSpec(
        key="AUTH_PIN",
        te_transcript="నమస్కారం. పొలంరక్షకు స్వాగతం. దయచేసి మీ 4 నుండి 6 అంకెల పిన్ నంబర్ నొక్కండి.",
        en_transcript=(
            "Welcome to PolamRaksha. Please enter your 4 to 6 digit PIN followed by hash."
        ),
        audio_filename="auth_pin.wav",
    ),
    "MAIN_MENU": AudioPromptSpec(
        key="MAIN_MENU",
        te_transcript=(
            "పంట అమ్మడానికి 1 నొక్కండి. వేలం వివరాలు తెలుసుకోవడానికి 2 నొక్కండి. "
            "కొనుగోలు ఆఫర్ నిర్ధారించడానికి 3 నొక్కండి. పంట వివరాలు మార్చడానికి 4 నొక్కండి. "
            "అమ్మకాన్ని రద్దు చేయడానికి 5 నొక్కండి. సహాయం కోసం 0 నొక్కండి. మళ్లీ వినడానికి స్టార్ నొక్కండి."
        ),
        en_transcript=(
            "Press 1 to sell produce. Press 2 for auction details. "
            "Press 3 to confirm a purchase offer. Press 4 to update listing price. "
            "Press 5 to cancel sale. Press 0 for help. Press star to repeat."
        ),
        audio_filename="main_menu.wav",
    ),
    "SELL_SELECT_CROP": AudioPromptSpec(
        key="SELL_SELECT_CROP",
        te_transcript="పంటను ఎంచుకోండి: {crop_options}. మళ్లీ వినడానికి స్టార్ నొక్కండి.",
        en_transcript="Select crop: {crop_options}. Press star to repeat.",
        audio_filename="sell_select_crop.wav",
    ),
    "SELL_ENTER_QUANTITY": AudioPromptSpec(
        key="SELL_ENTER_QUANTITY",
        te_transcript="దయచేసి కిలోగ్రాములలో పరిమాణాన్ని నొక్కి హ్యాష్ నొక్కండి. మార్చడానికి స్టార్ నొక్కండి.",
        en_transcript="Enter quantity in kilograms followed by hash. Press star to go back.",
        audio_filename="sell_enter_quantity.wav",
    ),
    "SELL_ENTER_PRICE": AudioPromptSpec(
        key="SELL_ENTER_PRICE",
        te_transcript="కిలోకు కనీస ధర రూపాయలలో నొక్కి హ్యాష్ నొక్కండి. పరిమాణం మార్చడానికి స్టార్ నొక్కండి.",
        en_transcript=(
            "Enter minimum price per kg in rupees followed by hash. "
            "Press star to correct quantity."
        ),
        audio_filename="sell_enter_price.wav",
    ),
    "SELL_SELECT_URGENCY": AudioPromptSpec(
        key="SELL_SELECT_URGENCY",
        te_transcript=(
            "సేకరణ అత్యవసరం ఎంచుకోండి: 2 గంటల్లో 1 నొక్కండి, 6 గంటల్లో 2 నొక్కండి, "
            "12 గంటల్లో 3 నొక్కండి, 24 గంటల్లో 4 నొక్కండి."
        ),
        en_transcript=(
            "Select collection urgency: Press 1 for 2 hours, 2 for 6 hours, "
            "3 for 12 hours, 4 for 24 hours."
        ),
        audio_filename="sell_select_urgency.wav",
    ),
    "SELL_CONFIRM": AudioPromptSpec(
        key="SELL_CONFIRM",
        te_transcript=(
            "మీరు నమోదు చేసిన వివరాలు: పంట {crop_name}, పరిమాణం {quantity_kg} కిలోలు, "
            "కనీస ధర కిలోకు {price_inr} రూపాయలు, సేకరణ గడువు {deadline_ist}. "
            "నిర్ధారించడానికి 1 నొక్కండి. మార్చడానికి 2 లేదా స్టార్ నొక్కండి."
        ),
        en_transcript=(
            "Read-back: Crop {crop_name}, quantity {quantity_kg} kg, "
            "floor price {price_inr} rupees/kg, collection deadline {deadline_ist}. "
            "Press 1 to confirm, 2 or star to correct."
        ),
        audio_filename="sell_confirm.wav",
    ),
    "SELL_CREATED": AudioPromptSpec(
        key="SELL_CREATED",
        te_transcript="మీ పంట జాబితా నమోదైంది. జాబితా సంఖ్య {short_id}. వేలం ప్రారంభమైంది.",
        en_transcript=(
            "Your produce listing is published. Reference ID {short_id}. Auction is now open."
        ),
        audio_filename="sell_created.wav",
    ),
    "AUCTION_STATUS": AudioPromptSpec(
        key="AUCTION_STATUS",
        te_transcript="ప్రస్తుత వేలం స్థితి: {summary}. ప్రధాన మెనూకు 1 నొక్కండి.",
        en_transcript="Auction status: {summary}. Press 1 for main menu.",
        audio_filename="auction_status.wav",
    ),
    "OFFER_APPROVAL": AudioPromptSpec(
        key="OFFER_APPROVAL",
        te_transcript=(
            "ఆఫర్ వివరాలు: పంట {crop_name}, కేటాయించిన పరిమాణం {qty_kg} కిలోలు, "
            "మొత్తం విలువ {gross_inr} రూపాయలు, రవాణా ఖర్చు {transport_inr} రూపాయలు, "
            "నికర ఆదాయం {net_inr} రూపాయలు, సేకరణ గడువు {deadline_ist}. "
            "ఆమోదించడానికి 1 నొక్కండి, తిరస్కరించడానికి 2 నొక్కండి, సహాయానికి 0 నొక్కండి."
        ),
        en_transcript=(
            "Offer summary: Crop {crop_name}, allocated {qty_kg} kg, gross {gross_inr} INR, "
            "transport {transport_inr} INR, estimated net {net_inr} INR, deadline {deadline_ist}. "
            "Press 1 to approve, 2 to reject, 0 for assisted support."
        ),
        audio_filename="offer_approval.wav",
    ),
    "OFFER_APPROVED": AudioPromptSpec(
        key="OFFER_APPROVED",
        te_transcript="ఆఫర్ ఆమోదించబడింది. ఆర్డర్లు సృష్టించబడ్డాయి.",
        en_transcript="Offer approved and orders created.",
        audio_filename="offer_approved.wav",
    ),
    "NO_PENDING_OFFER": AudioPromptSpec(
        key="NO_PENDING_OFFER",
        te_transcript="ప్రస్తుతం ఆమోదించాల్సిన కొనుగోలు ఆఫర్లు లేవు. ప్రధాన మెనూకు ఏదైనా కీ నొక్కండి.",
        en_transcript="No pending purchase offers to approve. Press any key for main menu.",
        audio_filename="no_pending_offer.wav",
    ),
    "HELP": AudioPromptSpec(
        key="HELP",
        te_transcript="సహాయం కోసం మీ సమీప పొలంరక్ష ఆపరేటర్ కేంద్రాన్ని సంప్రదించండి.",
        en_transcript="For assistance, contact your local PolamRaksha operator centre.",
        audio_filename="help.wav",
    ),
    "INVALID_INPUT": AudioPromptSpec(
        key="INVALID_INPUT",
        te_transcript="తప్పు ఎంపిక. దయచేసి మళ్లీ ప్రయత్నించండి.",
        en_transcript="Invalid input. Please try again.",
        audio_filename="invalid_input.wav",
    ),
    "SESSION_EXPIRED": AudioPromptSpec(
        key="SESSION_EXPIRED",
        te_transcript="సెషన్ గడువు ముగిసింది. దయచేసి మళ్లీ కాల్ చేయండి.",
        en_transcript="Session expired. Please call again.",
        audio_filename="session_expired.wav",
    ),
}


def compose_number_tokens(number: int, language: str = "te") -> list[str]:
    """Decompose an integer into spoken audio prompt tokens (deterministic & testable)."""
    if number < 0:
        return ["minus", *compose_number_tokens(abs(number), language)]
    if number == 0:
        return ["0"]

    tokens: list[str] = []
    thousands = number // 1000
    rem = number % 1000
    if thousands > 0:
        tokens.extend([str(thousands), "1000"])
    hundreds = rem // 100
    tens_units = rem % 100
    if hundreds > 0:
        tokens.extend([str(hundreds), "100"])
    if tens_units > 0:
        if tens_units <= 20 or tens_units % 10 == 0:
            tokens.append(str(tens_units))
        else:
            tokens.append(str((tens_units // 10) * 10))
            tokens.append(str(tens_units % 10))
    return tokens


def build_prompt_payload(
    *,
    prompt_key: str,
    language: str = "te",
    params: dict[str, Any] | None = None,
    dynamic_numbers: list[int] | None = None,
) -> dict[str, Any]:
    spec = PROMPT_CATALOG.get(prompt_key, PROMPT_CATALOG["HELP"])
    template = spec.te_transcript if language.startswith("te") else spec.en_transcript
    transcript = template.format(**(params or {}))
    lang_dir = "te" if language.startswith("te") else "en"
    number_tokens: list[str] = []
    for n in dynamic_numbers or []:
        number_tokens.extend(compose_number_tokens(n, lang_dir))

    return {
        "prompt_key": spec.key,
        "language": lang_dir,
        "audio_url": f"/audio/{lang_dir}/{spec.audio_filename}",
        "audio_available": False,
        "transcript": transcript,
        "number_audio_tokens": number_tokens,
    }
