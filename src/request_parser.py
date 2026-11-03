"""Turn a client's plain-English request into cleaning settings.

A real chat needs an API key and a network call, and would still have to be
trusted not to invent behaviour. This does the part that is actually useful:
read the sentence, set the switches, and say plainly what it did - and what it
cannot do.

Everything here is deterministic and offline, so a demo never depends on Wi-Fi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class RequestPlan:
    """Settings a request asks for. ``None`` means "no opinion"."""

    keep_duplicates: bool | None = None
    country: str | None = None
    phone_format: str | None = None
    skip_email: bool = False
    skip_phone: bool = False
    header_row: int | None = None
    applied: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)

    @property
    def touched(self) -> bool:
        return bool(self.applied or self.unsupported)


def _has(text: str, *patterns: str) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


_UNSUPPORTED = [
    (r"verif(y|ication).{0,20}(email|mailbox)|check.{0,15}mailbox|email.{0,10}exists",
     "Checking whether an email address really exists needs a paid verification "
     "service - I only check the format."),
    (r"gst portal|verify.{0,15}gst|gst.{0,10}valid.{0,10}government",
     "GSTIN is checked for format only; I cannot look it up on the GST portal."),
    (r"\bmerge\b.{0,20}(row|contact|duplicat)",
     "I never merge rows automatically. Near-duplicates are listed on a review "
     "sheet so you can decide."),
    (r"\b(send|email|whatsapp)\b.{0,25}(file|result|report)",
     "I do not send files anywhere. You download the result and share it."),
    (r"translate|hindi|gujarati|marathi",
     "Names are compared in English/Latin script only."),
    (r"\b(crm|salesforce|hubspot|zoho)\b",
     "I do not connect to a CRM. Import the cleaned file into it yourself."),
]


def parse_request(text: str) -> RequestPlan:
    """Read one sentence and return the settings it implies."""
    plan = RequestPlan()
    raw = (text or "").strip()
    if not raw:
        return plan

    text = raw.lower()

    # --- duplicates -------------------------------------------------------
    if _has(text, r"(keep|retain|don'?t remove|do not remove|not remove|leave).{0,25}duplicat"):
        plan.keep_duplicates = True
        plan.applied.append("duplicates will be listed but kept")
    elif _has(text, r"remove.{0,25}duplicat|delet.{0,20}duplicat|dedup"):
        plan.keep_duplicates = False
        plan.applied.append("duplicates will be removed")

    # --- phone format -----------------------------------------------------
    if _has(text, r"digits only|only digits|no plus|without \+"):
        plan.phone_format = "digits"
        plan.applied.append("phone numbers written as digits only")
    elif _has(text, r"10 digit|ten digit|local format|without country|no country code"):
        plan.phone_format = "local"
        plan.applied.append("phone numbers written as 10 digits")
    elif _has(text, r"international|\+91|country code|e\.?164"):
        plan.phone_format = "e164"
        plan.applied.append("phone numbers written as +91XXXXXXXXXX")

    # --- country ----------------------------------------------------------
    if _has(text, r"united states|\busa\b|\bus\b.{0,10}(number|phone)|american"):
        plan.country = "US"
        plan.applied.append("phone numbers treated as US")
    elif _has(text, r"any country|other countr|outside india"):
        plan.country = "ANY"
        plan.applied.append("phone numbers accepted from any country")
    elif _has(text, r"\bindia\b|indian"):
        plan.country = "IN"
        plan.applied.append("phone numbers treated as Indian")

    # --- switch whole checks off -----------------------------------------
    if _has(text, r"(don'?t|do not|no need to|skip|without).{0,20}(check|validat).{0,15}(phone|mobile)|"
                 r"(ignore|leave).{0,15}(phone|mobile)|phone.{0,10}(is )?(fine|ok)"):
        plan.skip_phone = True
        plan.applied.append("phone numbers will not be checked")
    if _has(text, r"(don'?t|do not|no need to|skip|without).{0,20}(check|validat).{0,15}e-?mail|"
                 r"(ignore|leave).{0,15}e-?mail|e-?mail.{0,10}(is )?(fine|ok)"):
        plan.skip_email = True
        plan.applied.append("emails will not be checked")

    # --- header row -------------------------------------------------------
    header_match = (
        re.search(r"header[s]?.{0,12}row\s*(\d+)", text)
        or re.search(r"row\s*(\d+).{0,12}header", text)
        or re.search(r"start.{0,12}row\s*(\d+)", text)
    )
    if header_match:
        row = int(header_match.group(1))
        if 1 <= row <= 50:
            plan.header_row = row
            plan.applied.append(f"headers are on row {row}")
    elif _has(text, r"title row|logo row|heading row"):
        plan.header_row = 2
        plan.applied.append("headers are on row 2 (below a title row)")

    # --- asked for, but out of scope -------------------------------------
    for pattern, message in _UNSUPPORTED:
        if _has(text, pattern):
            plan.unsupported.append(message)

    # --- already done by default, but worth confirming back --------------
    if _has(text, r"\bgst(in)?\b") and not any("GST portal" in m for m in plan.unsupported):
        plan.applied.append("GSTIN, PAN and pincode will be checked where present")

    return plan


def describe(plan: RequestPlan) -> str:
    """One line for the UI, or an empty string when nothing was understood."""
    return " · ".join(plan.applied)
