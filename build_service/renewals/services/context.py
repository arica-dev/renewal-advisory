"""What Clasp already knows about the group the packet is for.

In production this would come from Clasp's API (GET /employers/{id},
GET /plans?group=..., GET /open_enrollment_windows). Here it comes from the
same synthetic sample groups the Renewal Advisor uses, so the two tools agree.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from renewal_advisor.census import generate_group
from renewal_advisor.recommender import tiered_strategy
from renewal_advisor.models import Group
from renewal_advisor.service import SAMPLES


def group_id_for(group_number: str | None) -> str | None:
    if not group_number:
        return None
    gid = group_number.strip().lower().replace("-", "_")
    return gid if gid in SAMPLES else None


def load_group(group_id: str) -> Group:
    s = SAMPLES[group_id]
    return generate_group(s.size, s.seed)


# The sample groups' current split, the same default the Renewal Advisor uses.
# Live: GET /plan_configurations/{id}/contribution_strategy for each plan.
CURRENT_EMPLOYEE_ONLY_PCT = "70.00"
CURRENT_DEPENDENT_PCT = "70.00"


def current_contribution() -> dict:
    s = tiered_strategy(Decimal(CURRENT_EMPLOYEE_ONLY_PCT), Decimal(CURRENT_DEPENDENT_PCT))
    return {
        "strategy_type": "benefit_split",
        "employee_only_pct": CURRENT_EMPLOYEE_ONLY_PCT,
        "dependent_pct": CURRENT_DEPENDENT_PCT,
        "tiers": {ct.value: {"contribution_type": r.contribution_type.value,
                             "contribution": f"{r.contribution:.2f}"}
                  for ct, r in s.employer_contribution.items()},
    }


def next_renewal(plan_year_start: date) -> date:
    return plan_year_start.replace(year=plan_year_start.year + 1)


def clasp_context(group_number: str | None) -> dict | None:
    gid = group_id_for(group_number)
    if gid is None:
        return None
    g = load_group(gid)
    return {
        "group_id": gid,
        "employer_name": SAMPLES[gid].name,
        "state": g.state,
        "plan_year_start": g.plan_year_start.isoformat(),
        "renewal_date": next_renewal(g.plan_year_start).isoformat(),
        "enrolled": len(g.enrolled_members),
        "contribution": current_contribution(),
        "plans": [{"id": p.id, "plan_name": p.plan_name, "metal_level": p.metal_level,
                   "deductible": str(p.deductible), "oop_max": str(p.oop_max),
                   "base_rate_21": str(p.base_rate_21),
                   "enrolled": sum(1 for m in g.enrolled_members if m.enrolled_plan == p.id)}
                  for p in g.plans],
    }
