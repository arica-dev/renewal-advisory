"""Turn an approved renewal into the Clasp API calls that build it.

For each renewal plan:
    POST /plans                        the new plan year's plan
    POST /plans/{id}/premiums          its age-banded rates (ages 0-64)
    POST /plan_configurations          eligibility rules for the plan
    POST /plan_configurations/{id}/contribution_strategy
                                       who pays what (benefit_split by coverage
                                       tier), so payroll deductions are right
then once:
    POST /open_enrollment_windows      the renewal open enrollment, with the
                                       old-plan -> new-plan mapping

IDs Clasp assigns on create are written as {{plans.<key>.id}} placeholders, in
dependency order. Every body is validated against the request schemas in
clasp_schema/requests.json before it is shown. Nothing is sent: this service
has no Clasp API key, so the output is the exact list of calls to make.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from jsonschema import Draft202012Validator, FormatChecker

from .money import band_ages, plan_attributes

SCHEMAS = Path(settings.BASE_DIR) / "clasp_schema" / "requests.json"

# What a real integration copies from the group's current plan configuration
# (GET /plan_configurations). The sample groups don't have one, so these are
# stated as assumptions in the output.
DEFAULT_WAITING_PERIOD = {"policy": "first_of_month", "period": "day", "duration": 30,
                          "allow_coinciding_start": False}


@lru_cache(maxsize=1)
def operations() -> dict:
    return json.loads(SCHEMAS.read_text())["operations"]


def validate(operation: str, body) -> list[str]:
    v = Draft202012Validator(operations()[operation]["schema"], format_checker=FormatChecker())
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(body)'}: {e.message}"
            for e in sorted(v.iter_errors(body), key=lambda e: list(e.absolute_path))]


def premiums_body(rates: list[dict]) -> list[dict]:
    """One row per age 0-64 (Clasp's age-banded table; 64 covers 64 and older)."""
    by_age: dict[int, str] = {}
    for r in rates:
        for age in band_ages(r["label"]):
            by_age[age] = f"{Decimal(r['amount']):.2f}"
    return [{"age": str(a), "amount": by_age[a]} for a in sorted(by_age)]


COVERAGE_TIERS = ["member", "member_spouse", "member_child", "member_children", "member_family"]


def contribution_body(employee_only_pct, dependent_pct) -> dict:
    """Clasp 2026-04-24 shape: benefit_split, one rule per coverage tier."""
    def rule(pct):
        return {"contribution_type": "employer_percentage", "contribution": f"{Decimal(str(pct)):.2f}"}
    return {"strategy_type": "benefit_split",
            "employer_contribution": {t: rule(employee_only_pct if t == "member" else dependent_pct)
                                      for t in COVERAGE_TIERS}}


def _contribution_note(eo_pct, dep_pct, current: dict) -> str:
    chosen = f"{Decimal(str(eo_pct)):.0f}% employee-only, {Decimal(str(dep_pct)):.0f}% dependents"
    if (current and Decimal(str(eo_pct)) == Decimal(current.get("employee_only_pct", "-1"))
            and Decimal(str(dep_pct)) == Decimal(current.get("dependent_pct", "-1"))):
        return f"Contributions carry forward the group's current split ({chosen})."
    now = (f"{Decimal(current['employee_only_pct']):.0f}% / {Decimal(current['dependent_pct']):.0f}%"
           if current else "unknown")
    return f"Contributions changed to {chosen} (current split: {now}); payroll deductions will follow the new split."


def _usd0(x) -> str:
    return f"${Decimal(x):,.0f}"


def build_requests(packet: dict, ctx: dict, oe: dict, contribution: dict | None = None) -> dict:
    start = date.fromisoformat(packet["effective_date"])
    end = start.replace(year=start.year + 1) - timedelta(days=1)
    calls: list[dict] = []
    plan_refs, mapping = [], {}
    contribution = contribution or ctx.get("contribution") or {}
    eo_pct = contribution.get("employee_only_pct", "70.00")
    dep_pct = contribution.get("dependent_pct", "70.00")

    def add(op: str, path: str, body, purpose: str, depends_on: list[str] | None = None,
            ref: str | None = None):
        meta = operations()[op]
        calls.append({"id": f"{len(calls) + 1}", "operation": op, "method": meta["method"],
                      "path": path, "purpose": purpose, "ref": ref, "depends_on": depends_on or [],
                      "doc": meta["doc"], "body": body, "errors": validate(op, body)})

    for plan in packet["plans"]:
        if plan.get("status") == "discontinued":
            continue
        key = plan["key"]
        ref = f"{{{{plans.{key}.id}}}}"
        attrs = plan_attributes(plan["renewal_plan_name"])
        details = []
        if plan.get("deductible"):
            details.append({"label": "Deductible", "tooltip": None,
                            "info_lines": [f"{_usd0(plan['deductible'])} individual"]})
        if plan.get("oop_max"):
            details.append({"label": "Out-of-pocket max", "tooltip": None,
                            "info_lines": [f"{_usd0(plan['oop_max'])} individual"]})
        if plan.get("renewal_code"):
            details.append({"label": "Carrier plan code", "tooltip": None,
                            "info_lines": [plan["renewal_code"]]})
        body = {"plan_name": plan["renewal_plan_name"], "line_of_coverage": "medical",
                "group": ctx["group_id"], "effective_start": start.isoformat(),
                "effective_end": end.isoformat(), "premium_type": "age_banded",
                "hsa_eligible": attrs["hsa_eligible"], "plan_details": details}
        if attrs["plan_type"]:
            body["plan_type"] = attrs["plan_type"]
        if attrs["plan_type"] == "hmo":
            body["requires_primary_care_provider"] = True
        add("plan_create", "/plans", body, f"Create {plan['renewal_plan_name']} for "
            f"{start.year}", ref=ref)
        create_id = calls[-1]["id"]
        add("plan_premiums_create", f"/plans/{ref}/premiums", premiums_body(plan["rates"]),
            f"Load {plan['renewal_plan_name']} age-banded rates", [create_id])
        cfg_ref = f"{{{{plan_configurations.{key}.id}}}}"
        add("plan_configuration_create", "/plan_configurations",
            {"plan": ref, "waiting_period": dict(DEFAULT_WAITING_PERIOD),
             "dependent_age_limit": 26, "dependent_age_out_rule": "end_of_month"},
            f"Eligibility rules for {plan['renewal_plan_name']}", [create_id], ref=cfg_ref)
        cfg_id = calls[-1]["id"]
        add("plan_configuration_contribution_strategy_create",
            f"/plan_configurations/{cfg_ref}/contribution_strategy",
            contribution_body(eo_pct, dep_pct),
            f"Employer pays {Decimal(str(eo_pct)):.0f}% employee-only, {Decimal(str(dep_pct)):.0f}% "
            f"dependent tiers ({plan['renewal_plan_name']})", [cfg_id])
        plan_refs.append(ref)
        if plan.get("clasp_plan_id"):
            mapping[plan["clasp_plan_id"]] = ref

    metadata = {"source": "renewal-build", "carrier": packet.get("carrier") or "",
                "carrier_group_number": packet.get("group_number") or ""}
    for old, new in mapping.items():
        metadata[f"maps_to.{old}"[:40]] = new
    add("open_enrollment_window_create", "/open_enrollment_windows",
        {"employer": ctx["group_id"], "start_date": oe["start_date"], "end_date": oe["end_date"],
         "plans": plan_refs, "enrollment_type": oe["enrollment_type"], "metadata": metadata},
        f"Open enrollment for the {start.year} renewal",
        [c["id"] for c in calls if c["operation"] in ("plan_create", "plan_configuration_contribution_strategy_create")])

    return {
        "api_version": settings.CLASP_API_VERSION,
        "headers": {"Authorization": "Bearer $CLASP_API_KEY",
                    "Clasp-Version": settings.CLASP_API_VERSION,
                    "Content-Type": "application/json"},
        "requests": calls,
        "valid": all(not c["errors"] for c in calls),
        "assumptions": [
            _contribution_note(eo_pct, dep_pct, ctx.get("contribution") or {}),
            "Waiting period and dependent age rules use common defaults; a live integration copies "
            "them from the group's current plan configuration.",
            "Enrollment is passive: members keep their elections and move to the mapped plan "
            "unless they make a change." if oe["enrollment_type"] == "passive" else
            "Enrollment is active: every member must make an election.",
            "Plan IDs are placeholders, filled in from each create response in order.",
        ],
    }
