"""ACA age rating.

Federal default age curve (effective plan years 2018+), per the HHS/CMS
standard age curve. Source: CMS "State Specific Age Curve Variations" and the
KFF copy of the 2018 revised HHS age factors (see docs/DATA_SOURCES.md).

Some states use their own curve (e.g. DC, MA, MN, NJ, OR, UT) and some are
community rated with no age rating (e.g. NY, VT). Start with a state that uses
the default curve, or add that state's curve here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

FEDERAL_DEFAULT: dict[int, Decimal] = {
    **{a: Decimal("0.765") for a in range(0, 15)},
    15: Decimal("0.833"), 16: Decimal("0.859"), 17: Decimal("0.885"),
    18: Decimal("0.913"), 19: Decimal("0.941"), 20: Decimal("0.970"),
    21: Decimal("1.000"), 22: Decimal("1.000"), 23: Decimal("1.000"), 24: Decimal("1.000"),
    25: Decimal("1.004"), 26: Decimal("1.024"), 27: Decimal("1.048"), 28: Decimal("1.087"),
    29: Decimal("1.119"), 30: Decimal("1.135"), 31: Decimal("1.159"), 32: Decimal("1.183"),
    33: Decimal("1.198"), 34: Decimal("1.214"), 35: Decimal("1.222"), 36: Decimal("1.230"),
    37: Decimal("1.238"), 38: Decimal("1.246"), 39: Decimal("1.262"), 40: Decimal("1.278"),
    41: Decimal("1.302"), 42: Decimal("1.325"), 43: Decimal("1.357"), 44: Decimal("1.397"),
    45: Decimal("1.444"), 46: Decimal("1.500"), 47: Decimal("1.563"), 48: Decimal("1.635"),
    49: Decimal("1.706"), 50: Decimal("1.786"), 51: Decimal("1.865"), 52: Decimal("1.952"),
    53: Decimal("2.040"), 54: Decimal("2.135"), 55: Decimal("2.230"), 56: Decimal("2.333"),
    57: Decimal("2.437"), 58: Decimal("2.548"), 59: Decimal("2.603"), 60: Decimal("2.714"),
    61: Decimal("2.810"), 62: Decimal("2.873"), 63: Decimal("2.952"), 64: Decimal("3.000"),
}

# States known to use a non-default curve or no age rating. Guard against
# silently mis-rating them.
NON_DEFAULT_STATES = {"DC", "MA", "MN", "NJ", "OR", "UT", "NY", "VT"}


def age_on(dob: date, as_of: date) -> int:
    """Age in whole years on a given date."""
    return as_of.year - dob.year - ((as_of.month, as_of.day) < (dob.month, dob.day))


def age_factor(age: int, state: str | None = None) -> Decimal:
    if state and state.upper() in NON_DEFAULT_STATES:
        raise NotImplementedError(
            f"{state} does not use the federal default age curve; add its curve first.")
    if age < 0:
        raise ValueError("age must be non-negative")
    return FEDERAL_DEFAULT[min(age, 64)]
