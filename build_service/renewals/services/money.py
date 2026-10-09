"""Small parsing helpers shared by the extractors and checks."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
_MONEY = re.compile(r"-?\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)")


class ExtractionError(ValueError):
    """The document could not be read into a renewal packet."""


def money(value) -> Decimal:
    """'$1,234.50', 1234.5 or '1234.50' -> Decimal('1234.50')."""
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    m = _MONEY.search(str(value or ""))
    if not m:
        raise ExtractionError(f"No amount in {value!r}")
    try:
        return Decimal(m.group(1).replace(",", "")).quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as e:  # pragma: no cover
        raise ExtractionError(str(e)) from e


def parse_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ExtractionError(f"Unrecognised date {value!r}")


def band_ages(label: str) -> list[int]:
    """'0-14' -> [0..14], '64+' -> [64], '37' -> [37]."""
    s = str(label).strip()
    if m := re.fullmatch(r"(\d{1,2})\s*[-–]\s*(\d{1,2})", s):
        return list(range(int(m.group(1)), int(m.group(2)) + 1))
    if m := re.fullmatch(r"(\d{1,2})\s*\+", s):
        return [int(m.group(1))]
    if re.fullmatch(r"\d{1,2}", s):
        return [int(s)]
    raise ExtractionError(f"Unrecognised age band {label!r}")


def plan_attributes(name: str) -> dict:
    """What a plan name says about the plan, e.g. 'Bronze HSA 6000'."""
    n = name.lower()
    metal = next((m for m in ("platinum", "gold", "silver", "bronze") if m in n), None)
    plan_type = next((t for t in ("ppo", "hmo", "epo", "pos") if t in n.split()), None)
    hsa = "hsa" in n.split()
    return {"metal_level": metal, "plan_type": plan_type or ("hdhp" if hsa else None),
            "hsa_eligible": hsa}
