"""Goal-constrained recommender.

Searches a small grid of renewal options:
  plan design   : keep current elections, or move everyone to one plan
  contribution  : employer % for employee-only coverage x employer % for
                  tiers with dependents (Clasp benefit_split, per coverage_type)

keeps the options that meet the broker's goals, and returns the best option
within each plan design, so the top picks are genuinely different structures
rather than near-identical ones.

"Best" depends on the objective:
  protect_employees (default): treat the employer goal as a budget and, within
      it, minimise the total extra cost pushed onto employees
  lowest_employer_cost: minimise the employer's cost within the goals

If fewer designs meet the goals than `top_n`, the list is filled with the
closest misses, each showing which goal it missed and by how much. Cost is
not the whole story: moving to a cheaper plan usually means a higher
deductible, so the label always shows the plan design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .models import ContributionRule, ContributionStrategy, ContributionType, CoverageType, Group, Plan
from .scenarios import Comparison, Scenario, baseline, compare, evaluate

ZERO = Decimal("0")


@dataclass(frozen=True)
class Goals:
    max_employer_increase_pct: Decimal | None = None   # e.g. 5 -> at most +5% vs today
    max_employee_monthly_increase: Decimal | None = None  # e.g. 75 -> no one pays > $75/mo more
    min_employee_only_pct: Decimal = Decimal(50)       # common carrier minimum; confirm per carrier
    max_deductible: Decimal | None = None  # skip "move everyone" designs above this deductible


@dataclass(frozen=True)
class Candidate:
    design: str                  # "Keep current plans" or "Move everyone to <plan>"
    employee_only_pct: Decimal
    dependent_tiers_pct: Decimal
    comparison: Comparison
    violations: dict[str, Decimal] = field(default_factory=dict)  # goal -> amount missed
    target_plan_id: str | None = None  # None = keep current elections

    @property
    def feasible(self) -> bool:
        return not self.violations

    @property
    def label(self) -> str:
        return (f"{self.design}, employer pays {self.employee_only_pct}% employee-only / "
                f"{self.dependent_tiers_pct}% with dependents")


@dataclass(frozen=True)
class Recommendation:
    top: tuple[Candidate, ...]
    feasible: bool
    evaluated: int


def tiered_strategy(employee_only_pct: Decimal, dependent_pct: Decimal) -> ContributionStrategy:
    def rule(pct):
        return ContributionRule(contribution_type=ContributionType.employer_percentage,
                                contribution=pct)
    return ContributionStrategy(employer_contribution={
        ct: rule(employee_only_pct if ct == CoverageType.member else dependent_pct)
        for ct in CoverageType})


def _pct_grid(lo: int, hi: int, step: int) -> list[Decimal]:
    return [Decimal(p) for p in range(lo, hi + 1, step)]


def _violations(c: Comparison, goals: Goals) -> dict[str, Decimal]:
    v: dict[str, Decimal] = {}
    if goals.max_employer_increase_pct is not None and \
            c.employer_change_pct > goals.max_employer_increase_pct:
        v["employer_increase_pct"] = c.employer_change_pct - goals.max_employer_increase_pct
    if goals.max_employee_monthly_increase is not None and \
            c.max_employee_increase > goals.max_employee_monthly_increase:
        v["employee_monthly_increase"] = c.max_employee_increase - goals.max_employee_monthly_increase
    return v


def _miss_score(c: Candidate) -> Decimal:
    """Rough distance from feasibility: % points over + dollars over / 10."""
    return (c.violations.get("employer_increase_pct", ZERO)
            + c.violations.get("employee_monthly_increase", ZERO) / 10)


def recommend(group: Group, current_strategy: ContributionStrategy,
              renewal_rates: dict[str, Decimal], renewal_date: date, goals: Goals,
              extra_plans: tuple[Plan, ...] = (), step: int = 5, top_n: int = 3,
              objective: str = "protect_employees") -> Recommendation:
    base = evaluate(group, baseline(group, current_strategy))

    designs: list[tuple[str, dict[str, str], str | None]] = [("Keep current plans", {}, None)]
    for p in (*group.plans, *extra_plans):
        if goals.max_deductible is not None and p.deductible is not None \
                and p.deductible > goals.max_deductible:
            continue
        designs.append((f"Move everyone to {p.plan_name}", {q.id: p.id for q in group.plans}, p.id))

    emp_grid = [p for p in _pct_grid(50, 100, step) if p >= goals.min_employee_only_pct]
    dep_grid = _pct_grid(0, 100, step)

    candidates: list[Candidate] = []
    for design, mapping, target in designs:
        for e in emp_grid:
            for d in dep_grid:
                s = Scenario(design, renewal_rates, tiered_strategy(e, d), renewal_date,
                             mapping, extra_plans)
                c = compare(base, evaluate(group, s))
                candidates.append(Candidate(design, e, d, c, _violations(c, goals), target))

    if objective == "protect_employees":
        key = (lambda c: (c.comparison.total_employee_monthly_change,
                          c.comparison.employer_annual, -c.employee_only_pct,
                          -c.dependent_tiers_pct))
    elif objective == "lowest_employer_cost":
        key = (lambda c: (c.comparison.employer_annual, c.comparison.max_employee_increase,
                          -c.employee_only_pct, -c.dependent_tiers_pct))
    else:
        raise ValueError(f"Unknown objective {objective!r}")

    best_per_design: dict[str, Candidate] = {}
    for c in sorted((c for c in candidates if c.feasible), key=key):
        best_per_design.setdefault(c.design, c)
    top = sorted(best_per_design.values(), key=key)[:top_n]

    if len(top) < top_n:
        closest_per_design: dict[str, Candidate] = {}
        for c in sorted((c for c in candidates if not c.feasible and c.design not in best_per_design),
                        key=lambda c: (_miss_score(c), key(c))):
            closest_per_design.setdefault(c.design, c)
        top += sorted(closest_per_design.values(), key=_miss_score)[:top_n - len(top)]

    return Recommendation(tuple(top), bool(best_per_design), len(candidates))


def scenario_for(candidate: Candidate, group: Group, renewal_rates: dict[str, Decimal],
                 renewal_date: date, extra_plans: tuple[Plan, ...] = ()) -> Scenario:
    """Rebuild the Scenario behind a candidate (e.g. to show per-employee detail)."""
    mapping = {} if candidate.target_plan_id is None else \
        {p.id: candidate.target_plan_id for p in group.plans}
    return Scenario(candidate.design, renewal_rates,
                    tiered_strategy(candidate.employee_only_pct, candidate.dependent_tiers_pct),
                    renewal_date, mapping, extra_plans)
