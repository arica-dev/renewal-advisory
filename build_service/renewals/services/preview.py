"""Feed the reviewed rates into the Renewal Advisor engine.

The same breakdown the Advisor shows (aging vs. rate change), computed from the
rates in the packet rather than from a separate notice, so the build and the
analysis can't disagree.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from renewal_advisor.renewal import break_down_renewal

from .checks import implied_base_21
from .context import load_group


def renewal_preview(packet: dict, ctx: dict | None) -> dict | None:
    if ctx is None:
        return None
    rates: dict[str, Decimal] = {}
    for plan in packet["plans"]:
        base = implied_base_21(plan["rates"])
        if plan.get("clasp_plan_id") and base:
            rates[plan["clasp_plan_id"]] = base
    group = load_group(ctx["group_id"])
    if any(m.enrolled_plan not in rates for m in group.enrolled_members):
        return None
    b = break_down_renewal(group, rates, date.fromisoformat(ctx["renewal_date"]))
    return {
        "current_monthly": float(b.current_monthly), "renewal_monthly": float(b.renewal_monthly),
        "total_pct": float(b.total_pct), "aging_pct": float(b.aging_pct),
        "rate_pct": float(b.rate_pct), "pure_rate_pct": float(b.pure_rate_change_pct),
        "rates_21": {k: str(v) for k, v in rates.items()},
        "advisor_url": f"/groups/{ctx['group_id']}",
    }
