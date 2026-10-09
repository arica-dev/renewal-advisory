"""What Clasp already knows about the group the packet is for.

In production this would come from Clasp's API (GET /employers/{id},
GET /plans?group=..., GET /open_enrollment_windows). Here it comes from the
same synthetic sample groups the Renewal Advisor uses, so the two tools agree.
"""

from __future__ import annotations

from datetime import date

from renewal_advisor.census import generate_group
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
        "plans": [{"id": p.id, "plan_name": p.plan_name, "metal_level": p.metal_level,
                   "deductible": str(p.deductible), "oop_max": str(p.oop_max),
                   "base_rate_21": str(p.base_rate_21),
                   "enrolled": sum(1 for m in g.enrolled_members if m.enrolled_plan == p.id)}
                  for p in g.plans],
    }
