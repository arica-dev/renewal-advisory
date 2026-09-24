"""Age-rated premium calculation for ACA small group.

Each covered person is rated individually: premium = base_rate_21 x age factor,
rounded to the cent. Only the three oldest covered children under age 21 are
charged; children 21 and older are always charged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .age_curve import age_factor, age_on
from .models import Member, RelationshipCategory

CENT = Decimal("0.01")
MAX_RATED_CHILDREN_UNDER_21 = 3


def to_cents(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class RatedPerson:
    person_id: str
    category: RelationshipCategory
    age: int
    factor: Decimal
    premium: Decimal  # monthly, to the cent (0 if not charged)
    charged: bool


def rate_member(member: Member, base_rate_21: Decimal, as_of: date,
                state: str | None = None) -> list[RatedPerson]:
    """Rate the employee and every covered dependent on `as_of`."""
    people: list[tuple[str, RelationshipCategory, date]] = [
        (member.id, RelationshipCategory.member, member.dob)]
    if member.spouse:
        people.append((member.spouse.id, RelationshipCategory.spouse, member.spouse.dob))

    kids = sorted(member.children, key=lambda d: d.dob)  # oldest first
    under_21_seen = 0
    kid_rows: list[tuple[str, RelationshipCategory, date, bool]] = []
    for kid in kids:
        charged = True
        if age_on(kid.dob, as_of) < 21:
            under_21_seen += 1
            charged = under_21_seen <= MAX_RATED_CHILDREN_UNDER_21
        kid_rows.append((kid.id, RelationshipCategory.child, kid.dob, charged))

    rated: list[RatedPerson] = []
    for pid, cat, dob in people:
        age = age_on(dob, as_of)
        f = age_factor(age, state)
        rated.append(RatedPerson(pid, cat, age, f, to_cents(base_rate_21 * f), True))
    for pid, cat, dob, charged in kid_rows:
        age = age_on(dob, as_of)
        f = age_factor(age, state)
        prem = to_cents(base_rate_21 * f) if charged else Decimal("0.00")
        rated.append(RatedPerson(pid, cat, age, f, prem, charged))
    return rated


def member_premium(member: Member, base_rate_21: Decimal, as_of: date,
                   state: str | None = None) -> Decimal:
    """Total monthly premium for a member's enrolled coverage."""
    return sum((p.premium for p in rate_member(member, base_rate_21, as_of, state)),
               Decimal("0.00"))
