"""Renewal breakdown: how much of an increase is the carrier's rate change vs.
the group getting older, and how it compares with the carrier's public filing.

Exact additive decomposition (every term uses the same per-person rounding):

    current       = sum premium(old base rate, ages at current plan year)
    aged_old_rate = sum premium(old base rate, ages at renewal date)
    renewal       = sum premium(new base rate, ages at renewal date)

    aging effect  = aged_old_rate - current
    rate effect   = renewal - aged_old_rate
    total change  = renewal - current = aging + rate   (exactly)

Assumes the same census and plan elections before and after renewal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .models import Group
from .rating import member_premium

HUNDRED = Decimal(100)


@dataclass(frozen=True)
class RenewalBreakdown:
    current_monthly: Decimal
    renewal_monthly: Decimal
    aging_effect: Decimal
    rate_effect: Decimal

    @property
    def total_change(self) -> Decimal:
        return self.renewal_monthly - self.current_monthly

    def pct(self, amount: Decimal) -> Decimal:
        return (amount / self.current_monthly * HUNDRED).quantize(Decimal("0.01"))

    @property
    def total_pct(self) -> Decimal:
        return self.pct(self.total_change)

    @property
    def aging_pct(self) -> Decimal:
        return self.pct(self.aging_effect)

    @property
    def rate_pct(self) -> Decimal:
        return self.pct(self.rate_effect)

    @property
    def pure_rate_change_pct(self) -> Decimal:
        """Rate change with aging removed (rate effect / aged premium at old
        rates). Comparable to a carrier's filed average rate change."""
        aged = self.current_monthly + self.aging_effect
        return (self.rate_effect / aged * HUNDRED).quantize(Decimal("0.01"))


def _group_total(group: Group, rates: dict[str, Decimal], as_of: date) -> Decimal:
    total = Decimal("0.00")
    for m in group.enrolled_members:
        total += member_premium(m, rates[m.enrolled_plan], as_of, group.state)
    return total


def break_down_renewal(group: Group, renewal_rates: dict[str, Decimal],
                       renewal_date: date) -> RenewalBreakdown:
    """`renewal_rates` maps plan id -> new base_rate_21."""
    current_rates = {p.id: p.base_rate_21 for p in group.plans}
    current = _group_total(group, current_rates, group.plan_year_start)
    aged = _group_total(group, current_rates, renewal_date)
    renewal = _group_total(group, renewal_rates, renewal_date)
    return RenewalBreakdown(current_monthly=current, renewal_monthly=renewal,
                            aging_effect=aged - current, rate_effect=renewal - aged)


@dataclass(frozen=True)
class Benchmark:
    group_rate_pct: Decimal      # rate-driven part of this group's increase
    filed_avg_pct: Decimal       # carrier's filed average for the market
    gap_pct: Decimal             # positive = group got more than the filing

    @property
    def flag(self) -> bool:
        return self.gap_pct > 0


def benchmark(breakdown: RenewalBreakdown, filed_avg_pct: Decimal) -> Benchmark:
    """Compare the rate-driven part of the increase (aging removed) with the
    carrier's filed average rate change. A filed average is a market-wide
    benchmark, not proof that a specific group's renewal is wrong."""
    g = breakdown.pure_rate_change_pct
    return Benchmark(group_rate_pct=g, filed_avg_pct=filed_avg_pct, gap_pct=g - filed_avg_pct)
