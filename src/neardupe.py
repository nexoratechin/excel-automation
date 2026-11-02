"""Find likely duplicates that survive exact matching.

Exact matching catches ``rahul@gmail.com`` twice. It does not catch
``Rahul Sharma`` next to ``Rahul S.``, which is the duplicate that actually
costs a client money when they pay per lead.

Nothing here deletes a row. The result is a review sheet: "these two look like
the same person, you decide". That is deliberate - merging different people
silently is worse than leaving a duplicate in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

import pandas as pd

TITLES = {"mr", "mrs", "ms", "miss", "dr", "shri", "smt", "sri", "prof", "sir", "madam"}
PUNCT = re.compile(r"[^a-z0-9 ]+")
TAG_WORDS = {"farms", "traders", "enterprises", "pvt", "ltd", "llp", "and", "co"}

DEFAULT_LIMIT = 2000
BLOCK_CAP = 250
COMPARISON_CAP = 400_000
MIN_RATIO = 0.88
SUBSET_RATIO = 0.55


@dataclass
class PossibleDuplicate:
    row_a: int
    row_b: int
    name_a: str
    name_b: str
    email_a: str
    email_b: str
    phone_a: str
    phone_b: str
    score: int
    reason: str


def normalize_name(value: str) -> str:
    """Lowercase, drop punctuation and honorifics, collapse spaces."""
    text = PUNCT.sub(" ", str(value).lower())
    tokens = [t for t in text.split() if t and t not in TITLES]
    return " ".join(tokens)


def _tokens(name: str) -> list[str]:
    return [t for t in name.split() if t]


def _token_eq(a: str, b: str) -> bool:
    """Compare two name parts, treating a single letter as an initial."""
    if a == b:
        return True
    if len(a) == 1 and b.startswith(a):
        return True
    if len(b) == 1 and a.startswith(b):
        return True
    return False


def _is_subset(small: list[str], big: list[str]) -> bool:
    return all(any(_token_eq(t, u) for u in big) for t in small)


def name_score(a: str, b: str) -> tuple[float, str]:
    """Return (similarity 0-1, human reason) for two normalised names."""
    if not a or not b:
        return 0.0, ""
    if a == b:
        return 1.0, "identical name"

    ratio = SequenceMatcher(None, a, b).ratio()
    ta, tb = _tokens(a), _tokens(b)

    if _is_subset(ta, tb) or _is_subset(tb, ta):
        shorter, longer = (ta, tb) if len(" ".join(ta)) <= len(" ".join(tb)) else (tb, ta)
        if any(len(t) == 1 for t in shorter):
            return max(ratio, 0.92), "same name, one part written as an initial"
        if len(shorter) == 1:
            return max(ratio, 0.9), "same first name, surname missing"
        return max(ratio, 0.9), "one name is part of the other"

    if ratio >= MIN_RATIO:
        return ratio, "names almost identical"
    return ratio, ""


def _block_key(name: str) -> str:
    return name[:3]


def find_possible_duplicates(
    rows: list[int],
    names: list[str],
    emails: list[str],
    phones: list[str],
    *,
    limit: int = DEFAULT_LIMIT,
    block_cap: int = BLOCK_CAP,
    comparison_cap: int = COMPARISON_CAP,
) -> pd.DataFrame:
    """Compare kept rows and return a review table. Never modifies the data."""
    columns = [
        "Row A", "Row B", "Name A", "Name B",
        "Email A", "Email B", "Phone A", "Phone B", "Score", "Why",
    ]

    prepared = []
    for i, name in enumerate(names):
        normalized = normalize_name(name)
        if not normalized:
            continue
        prepared.append((i, normalized, _block_key(normalized)))

    blocks: dict[str, list[int]] = {}
    for index, _normalized, key in prepared:
        blocks.setdefault(key, []).append(index)

    found: list[PossibleDuplicate] = []
    comparisons = 0

    for members in blocks.values():
        if len(members) < 2 or len(members) > block_cap:
            # A block this large is a common prefix, not useful evidence.
            continue
        for pos, i in enumerate(members):
            for j in members[pos + 1:]:
                if comparisons >= comparison_cap or len(found) >= limit:
                    break
                comparisons += 1

                score, reason = name_score(normalize_name(names[i]), normalize_name(names[j]))
                if not reason:
                    continue
                if emails[i] and emails[i] == emails[j]:
                    continue  # exact duplicates were already removed
                if phones[i] and phones[i] == phones[j]:
                    continue

                found.append(
                    PossibleDuplicate(
                        row_a=rows[i],
                        row_b=rows[j],
                        name_a=names[i],
                        name_b=names[j],
                        email_a=emails[i],
                        email_b=emails[j],
                        phone_a=phones[i],
                        phone_b=phones[j],
                        score=round(score * 100),
                        reason=reason,
                    )
                )

    if not found:
        return pd.DataFrame(columns=columns)

    found.sort(key=lambda item: (-item.score, item.row_a))
    frame = pd.DataFrame(
        [
            {
                "Row A": f.row_a,
                "Row B": f.row_b,
                "Name A": f.name_a,
                "Name B": f.name_b,
                "Email A": f.email_a,
                "Email B": f.email_b,
                "Phone A": f.phone_a,
                "Phone B": f.phone_b,
                "Score": f.score,
                "Why": f.reason,
            }
            for f in found
        ],
        columns=columns,
    )
    return frame
