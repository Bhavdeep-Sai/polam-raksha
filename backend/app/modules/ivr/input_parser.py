from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedDtmfInput:
    raw: str
    normalized: str
    is_repeat_or_back: bool
    is_help: bool
    numeric_value: int | None


def parse_dtmf_digits(raw_digits: str) -> ParsedDtmfInput:
    """Normalize and validate DTMF keypad input."""
    cleaned = raw_digits.strip()
    if cleaned == "*":
        return ParsedDtmfInput(
            raw=raw_digits,
            normalized="*",
            is_repeat_or_back=True,
            is_help=False,
            numeric_value=None,
        )
    if cleaned == "0":
        return ParsedDtmfInput(
            raw=raw_digits,
            normalized="0",
            is_repeat_or_back=False,
            is_help=True,
            numeric_value=0,
        )

    stripped = cleaned.rstrip("#")
    numeric: int | None = None
    if stripped.isdigit():
        numeric = int(stripped)

    return ParsedDtmfInput(
        raw=raw_digits,
        normalized=stripped,
        is_repeat_or_back=False,
        is_help=False,
        numeric_value=numeric,
    )

