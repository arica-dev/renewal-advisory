"""Employer / employee cost split under a Clasp-style benefit_split strategy."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import ContributionStrategy, ContributionType, CoverageType
from .rating import to_cents


@dataclass(frozen=True)
class CostSplit:
    total: Decimal
    employer: Decimal
    employee: Decimal


def split_cost(premium: Decimal, coverage_type: CoverageType,
               strategy: ContributionStrategy) -> CostSplit:
    rule = strategy.employer_contribution[coverage_type]
    if rule.contribution_type == ContributionType.employer_percentage:
        employer = to_cents(premium * rule.contribution / Decimal(100))
    elif rule.contribution_type == ContributionType.flat_employer_cost:
        employer = rule.contribution
    else:  # pragma: no cover - guarded by the enum
        raise NotImplementedError(rule.contribution_type)

    if rule.monthly_max_threshold is not None:
        employer = min(employer, rule.monthly_max_threshold)
    employer = min(employer, premium)  # employer never pays more than the premium
    return CostSplit(total=premium, employer=employer, employee=premium - employer)


def uniform_percentage_strategy(pct: Decimal | int | str) -> ContributionStrategy:
    """Convenience: the same employer % for every coverage tier."""
    from .models import ContributionRule

    rule = ContributionRule(contribution_type=ContributionType.employer_percentage,
                            contribution=Decimal(str(pct)))
    return ContributionStrategy(employer_contribution={ct: rule for ct in CoverageType})
