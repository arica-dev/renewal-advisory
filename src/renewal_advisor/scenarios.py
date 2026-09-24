"""Scenario engine: what each renewal option costs the employer and each employee.

A Scenario says, for the renewal plan year:
- which rate each plan has (`rates`, plan id -> base_rate_21),
- where each current plan's enrollees go (`plan_mapping`, default: stay put),
- how the employer contributes (`strategy`).

`evaluate` prices it per employee; `compare` diffs it against the baseline
(today's plans, rates, strategy and ages). The baseline uses the current plan
year's ages; renewal scenarios use ages on the renewal date, so aging is part
of every scenario's change, just as the employer will experience it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .contributions import split_cost
from .models import ContributionStrategy, CoverageType, Group, Plan
from .rating import member_premium

ZERO = Decimal("0.00")
TWELVE = Decimal(12)


@dataclass(frozen=True)
class Scenario:
    name: str
    rates: dict[str, Decimal]
    strategy: ContributionStrategy
    as_of: date
    plan_mapping: dict[str, str] = field(default_factory=dict)
    extra_plans: tuple[Plan, ...] = ()  # e.g. another carrier's quoted plans

    def target_plan(self, current_plan_id: str) -> str:
        return self.plan_mapping.get(current_plan_id, current_plan_id)


@dataclass(frozen=True)
class EmployeeCost:
    member_id: str
    name: str
    coverage_type: CoverageType
    plan_id: str
    total: Decimal
    employer: Decimal
    employee: Decimal


@dataclass(frozen=True)
class ScenarioResult:
    scenario: Scenario
    rows: tuple[EmployeeCost, ...]

    @property
    def total_monthly(self) -> Decimal:
        return sum((r.total for r in self.rows), ZERO)

    @property
    def employer_monthly(self) -> Decimal:
        return sum((r.employer for r in self.rows), ZERO)

    @property
    def employee_monthly(self) -> Decimal:
        return sum((r.employee for r in self.rows), ZERO)

    @property
    def employer_annual(self) -> Decimal:
        return self.employer_monthly * TWELVE

    def by_member(self) -> dict[str, EmployeeCost]:
        return {r.member_id: r for r in self.rows}

    def to_frame(self):
        import pandas as pd

        return pd.DataFrame([{
            "member_id": r.member_id, "name": r.name, "coverage_type": r.coverage_type.value,
            "plan_id": r.plan_id, "total": r.total, "employer": r.employer,
            "employee": r.employee} for r in self.rows])


def evaluate(group: Group, scenario: Scenario) -> ScenarioResult:
    known_plans = {p.id for p in group.plans} | {p.id for p in scenario.extra_plans}
    rows = []
    for m in group.enrolled_members:
        plan_id = scenario.target_plan(m.enrolled_plan)
        if plan_id not in known_plans:
            raise KeyError(f"Unknown plan {plan_id!r} in scenario {scenario.name!r}")
        premium = member_premium(m, scenario.rates[plan_id], scenario.as_of, group.state)
        split = split_cost(premium, m.coverage_type, scenario.strategy)
        rows.append(EmployeeCost(m.id, f"{m.first_name} {m.last_name}", m.coverage_type,
                                 plan_id, split.total, split.employer, split.employee))
    return ScenarioResult(scenario, tuple(rows))


# --- scenario builders ---------------------------------------------------------

def baseline(group: Group, strategy: ContributionStrategy) -> Scenario:
    return Scenario("Today", {p.id: p.base_rate_21 for p in group.plans}, strategy,
                    group.plan_year_start)


def accept_renewal(renewal_rates: dict[str, Decimal], strategy: ContributionStrategy,
                   renewal_date: date) -> Scenario:
    return Scenario("Accept renewal", dict(renewal_rates), strategy, renewal_date)


def move_all_to(plan_id: str, group: Group, renewal_rates: dict[str, Decimal],
                strategy: ContributionStrategy, renewal_date: date,
                extra_plans: tuple[Plan, ...] = ()) -> Scenario:
    mapping = {p.id: plan_id for p in group.plans}
    return Scenario(f"Move everyone to {plan_id}", dict(renewal_rates), strategy,
                    renewal_date, mapping, extra_plans)


def with_strategy(s: Scenario, strategy: ContributionStrategy, name: str) -> Scenario:
    return Scenario(name, s.rates, strategy, s.as_of, s.plan_mapping, s.extra_plans)


# --- comparison ----------------------------------------------------------------

@dataclass(frozen=True)
class Comparison:
    name: str
    employer_annual: Decimal
    employer_annual_change: Decimal
    employer_change_pct: Decimal
    employee_monthly_change: dict[str, Decimal]  # member id -> change

    @property
    def employees_paying_more(self) -> int:
        return sum(1 for v in self.employee_monthly_change.values() if v > 0)

    @property
    def total_employee_monthly_change(self) -> Decimal:
        return sum(self.employee_monthly_change.values(), ZERO)

    @property
    def max_employee_increase(self) -> Decimal:
        return max(self.employee_monthly_change.values(), default=ZERO)


def compare(base: ScenarioResult, other: ScenarioResult) -> Comparison:
    b, o = base.by_member(), other.by_member()
    if b.keys() != o.keys():
        raise ValueError("Scenarios must cover the same enrolled members")
    change = other.employer_annual - base.employer_annual
    pct = (change / base.employer_annual * 100).quantize(Decimal("0.01")) \
        if base.employer_annual else ZERO
    return Comparison(other.scenario.name, other.employer_annual, change, pct,
                      {k: o[k].employee - b[k].employee for k in b})
