"""Deterministic checks on an extracted renewal packet.

AI reads the document; this module verifies the numbers with plain rules:

- every age band 0-64 is present for every plan
- every rate fits the ACA federal default age curve (catches keying errors)
- every value was found in the document where the extractor said it was
- the effective date matches Clasp's renewal date for the group
- every plan Clasp has today is accounted for, and renamed or replaced plans
  are mapped by a person
- the packet's "current" rates match what Clasp has on file
- each plan's increase is compared with the public PA rate filings

Each flag says how bad it is:
  blocker  must be fixed or explicitly kept before requests are generated
  review   a person must confirm it
  info     context only
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from statistics import median

from renewal_advisor.age_curve import FEDERAL_DEFAULT, NON_DEFAULT_STATES
from renewal_advisor.filings import load_filings, market_summary
from renewal_advisor.rating import to_cents

from .extract import plan_key
from .money import ExtractionError, band_ages

ALL_AGES = set(range(0, 65))
LABEL_FOR_AGE = {0: "0-14", 64: "64+", **{a: str(a) for a in range(15, 64)}}
MAPPING_STATUSES = {"renamed", "replaced", "modified"}
CANNOT_KEEP = {"missing_age"}


def _flag(kind, severity, title, detail, plan=None, label=None, fix=None) -> dict:
    fid = ":".join(x for x in [kind, plan or "", label or ""] if x)
    return {"id": fid, "kind": kind, "severity": severity, "title": title, "detail": detail,
            "plan": plan, "label": label, "fix": fix, "can_keep": kind not in CANNOT_KEEP}


def _usd(x) -> str:
    return f"${Decimal(x):,.2f}"


def _swapped(a: Decimal, b: Decimal) -> bool:
    return a != b and sorted(f"{a:.2f}") == sorted(f"{b:.2f}")


def implied_base_21(rates: list[dict]) -> Decimal | None:
    """The plan's age-21 rate: printed if present, else the median implied by every row."""
    by_label = {r["label"]: Decimal(r["amount"]) for r in rates}
    if "21" in by_label:
        return by_label["21"]
    implied = []
    for r in rates:
        try:
            age = band_ages(r["label"])[0]
        except ExtractionError:
            continue
        implied.append(Decimal(r["amount"]) / FEDERAL_DEFAULT[min(age, 64)])
    return to_cents(Decimal(median(implied))) if implied else None


def check_rates(plan: dict, state: str | None) -> list[dict]:
    key = plan["key"]
    flags = []
    covered: set[int] = set()
    for r in plan["rates"]:
        try:
            covered |= set(band_ages(r["label"]))
        except ExtractionError:
            flags.append(_flag("bad_label", "blocker", f"Unreadable age band '{r['label']}'",
                               "The row's age band couldn't be interpreted.", key, r["label"]))
    base = implied_base_21(plan["rates"])
    for age in sorted(ALL_AGES - covered - set(range(1, 15))):
        if age == 0 and covered & set(range(0, 15)):
            continue
        label = LABEL_FOR_AGE[age]
        fix = {"action": "add_rate", "label": label,
               "amount": str(to_cents(base * FEDERAL_DEFAULT[age]))} if base else None
        flags.append(_flag("missing_age", "blocker", f"No rate for age {label}",
                           "Every age band needs a rate before premiums can be loaded."
                           + (f" The age curve gives {_usd(fix['amount'])}." if fix else ""),
                           key, label, fix))
    if base is None:
        return flags
    if state and state.upper() in NON_DEFAULT_STATES:
        flags.append(_flag("curve_unknown", "review", "State uses its own age curve",
                           f"{state} doesn't use the federal default curve, so rates weren't "
                           "checked against it.", key))
        return flags

    misfits = []
    for r in plan["rates"]:
        try:
            age = band_ages(r["label"])[0]
        except ExtractionError:
            continue
        expected = to_cents(base * FEDERAL_DEFAULT[min(age, 64)])
        printed = Decimal(r["amount"])
        if abs(printed - expected) > Decimal("0.01"):
            misfits.append((r, printed, expected))
    if len(misfits) > len(plan["rates"]) // 3:
        flags.append(_flag("curve_mismatch", "review", "Rates don't follow the federal age curve",
                           f"{len(misfits)} of {len(plan['rates'])} rates differ from the federal "
                           "default curve. The carrier may use a different curve; check the "
                           "state's rating rules.", key))
        return flags
    for r, printed, expected in misfits:
        why = (" The digits look swapped, which suggests a keying error."
               if _swapped(printed, expected) else "")
        flags.append(_flag(
            "age_curve", "blocker", f"Age {r['label']} rate doesn't fit the age curve",
            f"Printed {_usd(printed)}; the plan's age-21 rate ({_usd(base)}) times the age "
            f"factor gives {_usd(expected)}.{why}", key, r["label"],
            {"action": "set_rate", "label": r["label"], "amount": str(expected)}))
    return flags


def check_grounding(plan: dict) -> list[dict]:
    missing = [r for r in plan["rates"]
               if not r.get("source", {}).get("verified", True) and not r.get("source", {}).get("edited")]
    if not missing:
        return []
    labels = ", ".join(r["label"] for r in missing[:6]) + ("…" if len(missing) > 6 else "")
    return [_flag("unverified", "blocker", f"{len(missing)} rate(s) not found in the document",
                  f"Ages {labels}: the value wasn't found where the extractor said it was "
                  "printed. Check them against the original before using them.", plan["key"])]


def check_against_clasp(packet: dict, ctx: dict) -> list[dict]:
    flags = []
    renewal_date = ctx["renewal_date"]
    if packet.get("effective_date") != renewal_date:
        flags.append(_flag(
            "effective_date", "blocker", "Effective date doesn't match Clasp",
            f"The packet says {date.fromisoformat(packet['effective_date']):%b %-d, %Y}; Clasp's "
            f"renewal date for this group is {date.fromisoformat(renewal_date):%b %-d, %Y}. "
            "Confirm with the carrier which is right.", fix={"action": "set_effective_date",
                                                          "value": renewal_date}))
    by_name = {p["current_plan_name"]: p for p in packet["plans"]}
    for cp in ctx["plans"]:
        pp = by_name.get(cp["plan_name"])
        if pp is None:
            flags.append(_flag("plan_missing", "blocker", f"{cp['plan_name']} isn't in the packet",
                               f"{cp['enrolled']} enrolled member(s) are on this plan today. Ask the "
                               "carrier whether it renews or what replaces it.", cp["id"]))
            continue
        pp["clasp_plan_id"] = cp["id"]
        if pp.get("current_rate_21") and Decimal(pp["current_rate_21"]) != Decimal(cp["base_rate_21"]):
            flags.append(_flag(
                "current_rate", "review", f"{cp['plan_name']}: current rate differs from Clasp",
                f"The packet lists today's age-21 rate as {_usd(pp['current_rate_21'])}; Clasp has "
                f"{_usd(cp['base_rate_21'])}. The increase is calculated from Clasp's rate.",
                pp["key"]))
        for fld, label in (("deductible", "deductible"), ("oop_max", "out-of-pocket max")):
            if pp.get(fld) and Decimal(pp[fld]) != Decimal(cp[fld]):
                flags.append(_flag(
                    "benefit_change", "review", f"{pp['renewal_plan_name']}: {label} changes",
                    f"{_usd(cp[fld])} today, {_usd(pp[fld])} at renewal. Members should be told "
                    "during open enrollment.", pp["key"], fld))
    return flags


def check_mapping(plan: dict) -> list[dict]:
    status = plan.get("status")
    if status in MAPPING_STATUSES:
        return [_flag("mapping", "review",
                      f"Confirm {plan['current_plan_name']} → {plan['renewal_plan_name']}",
                      f"The carrier marks this plan as {status}. Members on {plan['current_plan_name']} "
                      f"will be moved to {plan['renewal_plan_name']}. {plan.get('notes') or ''}".strip(),
                      plan["key"])]
    if status == "discontinued":
        return [_flag("discontinued", "blocker", f"{plan['current_plan_name']} is discontinued",
                      "No successor plan is named. Members need a plan to move to.", plan["key"])]
    return []


def check_market(plan: dict, ctx: dict | None) -> list[dict]:
    current = None
    if ctx and plan.get("clasp_plan_id"):
        current = next(Decimal(p["base_rate_21"]) for p in ctx["plans"] if p["id"] == plan["clasp_plan_id"])
    elif plan.get("current_rate_21"):
        current = Decimal(plan["current_rate_21"])
    base = implied_base_21(plan["rates"])
    if not current or not base:
        return []
    pct = (base / current - 1) * 100
    m = market_summary(load_filings())
    if pct > m.high_pct:
        sev, where = "review", f"above every PA carrier's average request ({m.low_pct:.1f}% to {m.high_pct:.1f}%)"
    elif pct > m.median_pct:
        sev, where = "info", f"above the PA median of {m.median_pct:.1f}%"
    else:
        sev, where = "info", f"at or below the PA median of {m.median_pct:.1f}%"
    return [_flag("market", sev, f"{plan['renewal_plan_name']}: +{pct:.1f}% rate change",
                  f"Age-21 rate {_usd(current)} → {_usd(base)}, {where}. "
                  "Filings are requested rates for 2027.", plan["key"])]


def run_checks(packet: dict, ctx: dict | None) -> list[dict]:
    for plan in packet["plans"]:
        plan.setdefault("key", plan_key(plan["renewal_plan_name"]))
    flags: list[dict] = []
    if ctx is None:
        flags.append(_flag("no_group", "review", "Not matched to a Clasp group",
                           f"No Clasp group has group number {packet.get('group_number') or '(none)'}. "
                           "Checks against current plans and the renewal date were skipped."))
    else:
        flags += check_against_clasp(packet, ctx)
    for plan in packet["plans"]:
        flags += check_grounding(plan) + check_rates(plan, packet.get("state")) + check_mapping(plan)
        flags += check_market(plan, ctx)
    order = {"blocker": 0, "review": 1, "info": 2}
    return sorted(flags, key=lambda f: order[f["severity"]])


def unresolved(flags: list[dict], kept: set[str]) -> list[dict]:
    """Flags still standing in the way of generating requests."""
    return [f for f in flags
            if (f["severity"] == "blocker" and not (f["can_keep"] and f["id"] in kept))
            or (f["severity"] == "review" and f["id"] not in kept)]
