"""Email and phone normalisation / validation.

Deliberately dependency-free: no DNS lookups, so the tool works offline on a
client machine and never stalls on a dead network.
"""

from __future__ import annotations

import re

# Characters Excel and copy-paste like to smuggle in.
INVISIBLES = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)

# Pragmatic email check: good enough to catch real typos without pretending to
# implement RFC 5322. Rejects consecutive dots and a leading/trailing dot.
EMAIL_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
                      r"@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
                      r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}$")

COUNTRY_RULES = {
    "IN": {"code": "91", "length": 10, "pattern": re.compile(r"^[6-9]\d{9}$"), "label": "Indian mobile"},
    "US": {"code": "1", "length": 10, "pattern": re.compile(r"^[2-9]\d{9}$"), "label": "US phone"},
    "ANY": {"code": None, "length": None, "pattern": re.compile(r"^\d{6,15}$"), "label": "phone number"},
}


def clean_text(value) -> str:
    """Trim, drop invisibles and non-breaking spaces, collapse inner runs.

    Empty cells arrive as None or NaN depending on the reader, and both must
    look blank rather than becoming the literal text "nan".
    """
    if value is None:
        return ""
    if isinstance(value, float) and value != value:  # NaN
        return ""
    text = str(value).replace("\xa0", " ").translate(INVISIBLES)
    return re.sub(r"\s+", " ", text).strip()


def normalize_email(value) -> tuple[str | None, str | None]:
    """Return (normalized_email, error). One of the two is always None."""
    if value is None or (isinstance(value, float) and value != value):
        return None, "empty"
    # Remove formatting artefacts, but a real space is a typo we cannot guess.
    text = str(value).replace("\xa0", "").translate(INVISIBLES).strip()
    if not text:
        return None, "empty"
    text = text.lower()
    if text.startswith("mailto:"):
        text = text[len("mailto:"):]
    if text.count("@") != 1:
        return None, "invalid email"
    if not EMAIL_RE.match(text):
        return None, "invalid email"
    return text, None


def normalize_phone(value, country: str = "IN", phone_format: str = "local") -> tuple[str | None, str | None]:
    """Return (normalized_phone, error). One of the two is always None."""
    raw = clean_text(value)
    if not raw:
        return None, "empty"

    rule = COUNTRY_RULES[country.upper()]
    had_plus = raw.startswith("+")
    # Keep digits only: strips spaces, dashes, brackets, dots, extensions text.
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None, "invalid phone"

    if rule["code"]:
        code = rule["code"]
        if len(digits) == rule["length"] + len(code) and digits.startswith(code):
            digits = digits[len(code):]
        elif len(digits) == rule["length"] + 1 and digits.startswith("0"):
            digits = digits[1:]
        elif len(digits) > rule["length"]:
            # Something like a trailing extension - keep the tail if it fits.
            if digits[-rule["length"]:].startswith("0"):
                return None, "invalid phone"
            digits = digits[-rule["length"]:]

    if rule["length"] and len(digits) != rule["length"]:
        return None, "invalid phone"
    if not rule["pattern"].match(digits):
        return None, "invalid phone"

    if phone_format == "digits" or not rule["code"]:
        return digits, None
    if phone_format == "e164":
        return f"+{rule['code']}{digits}", None
    # local
    return digits, None


def describe_phone_rule(country: str) -> str:
    return COUNTRY_RULES[country.upper()]["label"]
