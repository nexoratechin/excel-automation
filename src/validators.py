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

# 2-digit state code, 5 letters of the PAN, 4 digits, entity letter, 'Z', check char.
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
PINCODE_RE = re.compile(r"^[1-9][0-9]{5}$")

# 01-38 are the states and union territories; 97 and 99 are for online sellers.
VALID_GST_STATE_CODES = {f"{n:02d}" for n in range(1, 39)} | {"97", "99"}


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
    """Return (normalized_phone, error). One of the two is always None.

    Excel stores every number as a float, so a phone column always arrives as
    ``9876543210.0``. Stripping non-digits from that would produce
    ``98765432100`` and then silently keep the last ten digits -- a different,
    valid-looking number. Numeric input is therefore converted properly, and
    anything with a real fractional part or scientific notation is rejected
    rather than guessed at.
    """
    if value is None or (isinstance(value, float) and value != value):
        return None, "empty"

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if not number.is_integer():
            return None, "invalid phone"
        raw = str(int(number))
    else:
        raw = clean_text(value)
        if not raw:
            return None, "empty"
        if "e" in raw.lower():
            # 9.87654E+09 has already lost the real digits upstream.
            return None, "invalid phone"
        compact = re.sub(r"[^\d.]", "", raw)
        if "." in compact:
            if not re.fullmatch(r"\d+\.0*", compact):
                return None, "invalid phone"
            compact = compact.split(".")[0]
        if not compact:
            return None, "invalid phone"
        raw = compact

    rule = COUNTRY_RULES[country.upper()]
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


def _numeric_text(value) -> str | None:
    """Whole numbers from Excel arrive as floats; return them without '.0'."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if not number.is_integer():
            return None
        return str(int(number))
    return None


def normalize_gstin(value) -> tuple[str | None, str | None]:
    """Validate the 15-character GSTIN format.

    Format only -- the check digit is not recomputed and nothing is looked up on
    the GST portal, so a well-formed but fake number passes. Say so when selling.
    """
    text = _numeric_text(value) or clean_text(value)
    if not text:
        return None, "empty"
    text = text.upper().replace(" ", "").replace("-", "")
    if not GSTIN_RE.match(text):
        return None, "invalid GSTIN"
    if text[:2] not in VALID_GST_STATE_CODES:
        return None, "invalid GSTIN"
    return text, None


def normalize_pan(value) -> tuple[str | None, str | None]:
    text = _numeric_text(value) or clean_text(value)
    if not text:
        return None, "empty"
    text = text.upper().replace(" ", "").replace("-", "")
    if not PAN_RE.match(text):
        return None, "invalid PAN"
    return text, None


def normalize_pincode(value) -> tuple[str | None, str | None]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        text = _numeric_text(value)
        if text is None:
            return None, "invalid pincode"
    else:
        raw = clean_text(value)
        if not raw:
            return None, "empty"
        if "." in raw:
            # 400001.0 from a numeric cell, but 400001.5 is not a pincode.
            compact = re.sub(r"[^\d.]", "", raw)
            if not re.fullmatch(r"\d+\.0*", compact):
                return None, "invalid pincode"
            text = compact.split(".")[0]
        else:
            text = re.sub(r"\D", "", raw)
    if not PINCODE_RE.match(text):
        return None, "invalid pincode"
    return text, None
