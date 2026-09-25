"""Application service: everything the web front end asks for, as plain dicts.

Keeps the API layer (api/index.py) thin and testable without HTTP. All money is
returned as floats rounded to cents, percentages to 2 decimals.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from .census import generate_group
from .filings import against_carrier, against_market, load_filings, market_summary
from .ingest import parse_renewal_pdf
from .models import Group
from .recommender import Candidate, Goals, recommend, scenario_for, tiered_strategy
from .renewal import break_down_renewal
from .scenarios import accept_renewal, baseline, compare, evaluate

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
MARKET = "market"


@dataclass(frozen=True)
class SampleGroup:
    id: str
    size: int
    seed: int
    name: str
    status: str


# Fictional display names for the synthetic sample groups.
SAMPLES = {
    s.id: s for s in [
        SampleGroup("grp_30_2", 30, 2, "Linden Architecture", "In review"),
        SampleGroup("grp_45_3", 45, 3, "Kestrel Logistics", "Not started"),
        SampleGroup("grp_12_1", 12, 1, "Harbor Street Bakery", "Not started"),
    ]
}

COVERAGE_LABEL = {"member": "Employee only", "member_spouse": "Employee + spouse",
                  "member_child": "Employee + child", "member_children": "Employee + children",
                  "member_family": "Family"}


class NotFound(KeyError):
    pass


def f2(x: Decimal | float | int) -> float:
    return round(float(x), 2)


@lru_cache(maxsize=8)
def _load(group_id: str) -> tuple[Group, object]:
    s = SAMPLES.get(group_id)
    if s is None:
        raise NotFound(group_id)
    g = generate_group(s.size, s.seed)
    notice = parse_renewal_pdf(DATA / g.id / "renewal_notice.pdf")
    return g, notice


def _benchmark(pure_pct: Decimal, compare_to: str):
    filings = load_filings()
    if compare_to in ("", MARKET):
        return against_market(pure_pct, filings), MARKET
    match = next((f for f in filings if f.company == compare_to), None)
    if match is None:
        raise NotFound(compare_to)
    return against_carrier(pure_pct, match), compare_to


def list_groups(today: date | None = None) -> list[dict]:
    today = today or date.today()
    median = market_summary(load_filings()).median_pct
    out = []
    for s in SAMPLES.values():
        g, notice = _load(s.id)
        b = break_down_renewal(g, notice.renewal_rates(), notice.effective_date)
        bench, _ = _benchmark(b.pure_rate_change_pct, MARKET)
        out.append({
            "id": s.id, "name": s.name, "size": s.size, "enrolled": len(g.enrolled_members),
            "carrier": notice.carrier, "renewal_date": notice.effective_date.isoformat(),
            "days_to_renewal": (notice.effective_date - today).days,
            "current_monthly": f2(b.current_monthly), "renewal_monthly": f2(b.renewal_monthly),
            "added_annual": f2((b.renewal_monthly - b.current_monthly) * 12),
            "total_pct": f2(b.total_pct), "pure_rate_pct": f2(b.pure_rate_change_pct),
            "market_median_pct": f2(median), "verdict": bench.verdict, "status": s.status,
        })
    return out


def filings_payload() -> dict:
    fs = load_filings()
    m = market_summary(fs)
    return {
        "state": "PA", "market": "Small group", "plan_year": 2027, "retrieved": "2026-09-24",
        "source": "https://ratereview.healthcare.gov/", "requested_only": not m.all_final,
        "median_pct": f2(m.median_pct), "low_pct": f2(m.low_pct), "high_pct": f2(m.high_pct),
        "carriers": [{"company": f.company, "requested_pct": f2(f.requested_pct),
                      "range_low_pct": f2(f.range_low_pct), "range_high_pct": f2(f.range_high_pct),
                      "products": f.products, "status": f.status} for f in fs],
    }


def _employee_rows(g: Group, base_res, res) -> list[dict]:
    names = {p.id: p.plan_name for p in g.plans}
    before, after = base_res.by_member(), res.by_member()
    rows = [{
        "id": k, "name": before[k].name,
        "coverage": COVERAGE_LABEL[before[k].coverage_type.value],
        "plan_today": names[before[k].plan_id], "plan_renewal": names[after[k].plan_id],
        "pays_today": f2(before[k].employee), "pays_renewal": f2(after[k].employee),
        "change": f2(after[k].employee - before[k].employee),
    } for k in before]
    return sorted(rows, key=lambda r: -r["change"])


def _option(rank: int, c: Candidate, g: Group, base_res, rates, renewal_date) -> dict:
    res = evaluate(g, scenario_for(c, g, rates, renewal_date))
    plans = {p.id: p for p in g.plans}
    moved_up = 0
    target_deductible = None
    if c.target_plan_id:
        target = plans[c.target_plan_id]
        target_deductible = f2(target.deductible) if target.deductible is not None else None
        for m in g.enrolled_members:
            cur = plans[m.enrolled_plan]
            if (target.deductible or 0) > (cur.deductible or 0):
                moved_up += 1
    cm = c.comparison
    return {
        "rank": rank, "design": c.design, "target_plan_id": c.target_plan_id,
        "employee_only_pct": f2(c.employee_only_pct), "dependent_pct": f2(c.dependent_tiers_pct),
        "feasible": c.feasible,
        "violations": {k: f2(v) for k, v in c.violations.items()},
        "employer_annual": f2(cm.employer_annual), "employer_change_pct": f2(cm.employer_change_pct),
        "employees_paying_more": cm.employees_paying_more,
        "max_employee_increase": f2(max(cm.max_employee_increase, Decimal(0))),
        "total_employee_monthly_change": f2(cm.total_employee_monthly_change),
        "moved_to_higher_deductible": moved_up, "target_deductible": target_deductible,
        "employees": _employee_rows(g, base_res, res),
    }


def analysis(group_id: str, *, employee_only_pct: float = 70, dependent_pct: float = 70,
             max_employer_increase_pct: float = 5, max_employee_monthly_increase: float = 100,
             min_employee_only_pct: float = 50, max_deductible: float | None = None,
             objective: str = "protect_employees", compare_to: str = MARKET,
             today: date | None = None) -> dict:
    today = today or date.today()
    s = SAMPLES.get(group_id)
    if s is None:
        raise NotFound(group_id)
    g, notice = _load(group_id)
    rates = notice.renewal_rates()
    rdate = notice.effective_date
    D = lambda x: Decimal(str(x))  # noqa: E731

    b = break_down_renewal(g, rates, rdate)
    bench, compared = _benchmark(b.pure_rate_change_pct, compare_to)
    current = tiered_strategy(D(employee_only_pct), D(dependent_pct))
    base_res = evaluate(g, baseline(g, current))
    acc_res = evaluate(g, accept_renewal(rates, current, rdate))
    acc = compare(base_res, acc_res)
    goals = Goals(max_employer_increase_pct=D(max_employer_increase_pct),
                  max_employee_monthly_increase=D(max_employee_monthly_increase),
                  min_employee_only_pct=D(min_employee_only_pct),
                  max_deductible=None if max_deductible is None else D(max_deductible))
    rec = recommend(g, current, rates, rdate, goals, objective=objective)

    plans = [{"id": p.id, "name": p.plan_name, "metal": p.metal_level,
              "deductible": f2(p.deductible) if p.deductible is not None else None,
              "current_rate_21": f2(p.base_rate_21), "renewal_rate_21": f2(rates[p.id]),
              "change_pct": f2((rates[p.id] / p.base_rate_21 - 1) * 100),
              "enrolled": sum(1 for m in g.enrolled_members if m.enrolled_plan == p.id)}
             for p in g.plans]
    out = {
        "group": {"id": s.id, "name": s.name, "size": s.size, "enrolled": len(g.enrolled_members),
                  "carrier": notice.carrier, "renewal_date": rdate.isoformat(),
                  "days_to_renewal": (rdate - today).days, "state": g.state, "status": s.status},
        "plans": plans,
        "breakdown": {
            "current_monthly": f2(b.current_monthly), "renewal_monthly": f2(b.renewal_monthly),
            "aging": f2(b.aging_effect), "rate": f2(b.rate_effect),
            "total_change": f2(b.total_change), "total_pct": f2(b.total_pct),
            "aging_pct": f2(b.aging_pct), "rate_pct": f2(b.rate_pct),
            "pure_rate_change_pct": f2(b.pure_rate_change_pct),
        },
        "benchmark": {
            "compare_to": compared, "against": bench.against,
            "group_rate_pct": f2(bench.group_rate_pct), "reference_pct": f2(bench.reference_pct),
            "range_low_pct": f2(bench.range_low_pct), "range_high_pct": f2(bench.range_high_pct),
            "gap_pct": f2(bench.gap_pct), "verdict": bench.verdict, "requested": bench.requested,
        },
        "today": {"employer_annual": f2(base_res.employer_annual)},
        "accept_renewal": {"employer_annual": f2(acc.employer_annual),
                           "employer_change_pct": f2(acc.employer_change_pct),
                           "employees_paying_more": acc.employees_paying_more,
                           "max_employee_increase": f2(max(acc.max_employee_increase, Decimal(0))),
                           "employees": _employee_rows(g, base_res, acc_res)},
        "goals": {"max_employer_increase_pct": max_employer_increase_pct,
                  "max_employee_monthly_increase": max_employee_monthly_increase,
                  "min_employee_only_pct": min_employee_only_pct, "max_deductible": max_deductible,
                  "objective": objective, "employee_only_pct": employee_only_pct,
                  "dependent_pct": dependent_pct},
        "search": {"evaluated": rec.evaluated, "any_feasible": rec.feasible},
        "options": [_option(i, c, g, base_res, rates, rdate) for i, c in enumerate(rec.top, 1)],
    }
    out["takeaways"] = takeaways(out)
    out["summary"] = summary(out)
    return out


def _lower1(s: str) -> str:
    return s[:1].lower() + s[1:]


def _usd(x: float) -> str:
    return f"${x:,.2f}" if x != int(x) else f"${x:,.0f}"


def _contribution(o: dict) -> str:
    eo, dep = o["employee_only_pct"], o["dependent_pct"]
    if eo == dep:
        return f"the employer paying {eo:g}% for every tier"
    return f"the employer paying {eo:g}% for employee-only and {dep:g}% for family tiers"


def summary(a: dict) -> str:
    """One-sentence headline for the Bottom line card."""
    bm = a["benchmark"]
    feasible = a["search"]["any_feasible"]
    ref = "the market" if bm["compare_to"] == MARKET else f"{bm['against']}'s filing"
    if bm["verdict"] == "above_range":
        return f"Push back first: the rate change is above every product in {ref}."
    if bm["verdict"] == "above_average":
        lead = f"Push back first: the rate change is {bm['gap_pct']:.1f} points above {ref}"
        return lead + ("." if feasible else ", and no plan change meets the goals at this rate.")
    return (f"The rate change is in line with {ref}, so the decision is about plan and contribution."
            if feasible else
            f"The rate change is in line with {ref}, and no option meets every goal yet.")


def takeaways(a: dict) -> list[dict]:
    """Three plain-language conclusions built only from the computed figures.

    why: aging vs. rate change. fair: benchmark verdict. do: what to take to the employer.
    """
    b, bm, goals = a["breakdown"], a["benchmark"], a["goals"]
    enrolled = a["group"]["enrolled"]
    market = bm["compare_to"] == MARKET
    ref_name = "the PA median" if market else f"{bm['against']}'s filed average"
    filed = "requested" if bm["requested"] else "approved"

    why = (f"Of the +{b['total_pct']:.1f}%, {b['aging_pct']:.1f} points is employees aging into "
           f"higher age bands, which can't be negotiated. The other {b['rate_pct']:.1f} points "
           f"is the carrier's rate change.")

    rate = f"With aging removed, the carrier raised rates {bm['group_rate_pct']:.1f}%"
    ref = f"{ref_name} of {bm['reference_pct']:.1f}% {filed} for 2027"
    if bm["verdict"] == "above_range":
        fair = (f"{rate}, above every product in {bm['against']}'s filing "
                f"({bm['range_low_pct']:.1f}% to {bm['range_high_pct']:.1f}%).")
    elif bm["verdict"] == "above_average":
        fair = f"{rate}, {bm['gap_pct']:.1f} points above {ref}."
    else:
        where = ("in line with" if abs(bm["gap_pct"]) < 0.05
                 else f"{abs(bm['gap_pct']):.1f} points below")
        fair = (f"{rate}, {where} {ref}. Negotiating leverage is limited, "
                f"so plan and contribution options matter more.")

    push = bm["verdict"] != "within"
    opts = a["options"]
    best = opts[0] if opts else None
    if best and best["feasible"]:
        n = best["employees_paying_more"]
        who = ("no employee pays more" if n == 0 else
               f"only {n} of {enrolled} employees {'pays' if n == 1 else 'pay'} more "
               f"(at most {_usd(best['max_employee_increase'])}/month)")
        do = ("If the carrier won't lower the rate, the best option is to "
              if push else "The best option is to ")
        do += (f"{_lower1(best['design'])}, with {_contribution(best)}. That keeps the employer "
               f"at {best['employer_change_pct']:+.1f}%, and {who}.")
        if best["moved_to_higher_deductible"] and best["target_deductible"] is not None:
            m = best["moved_to_higher_deductible"]
            do += (f" The tradeoff: {m} of {enrolled} employees move to a "
                   f"{_usd(best['target_deductible'])} deductible.")
    else:
        do = "No plan and contribution mix meets every goal."
        if best:
            misses = []
            if "employer_increase_pct" in best["violations"]:
                misses.append(f"leaves the employer at {best['employer_change_pct']:+.1f}% against "
                              f"a {goals['max_employer_increase_pct']:+g}% budget")
            if "employee_monthly_increase" in best["violations"]:
                misses.append(f"adds up to {_usd(best['max_employee_increase'])}/month for one "
                              f"employee against a {_usd(goals['max_employee_monthly_increase'])} cap")
            if misses:
                do += f" The closest option ({_lower1(best['design'])}) still {' and '.join(misses)}."
        do += (" Negotiating the rate down is the main lever." if push
               else " Relaxing a goal is the way to open up options.")

    return [
        {"id": "why", "title": "Why it went up", "text": why},
        {"id": "fair", "title": "Is it fair", "text": fair},
        {"id": "do", "title": "What to do", "text": do},
    ]


def _long_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


def escape_markup(s: str) -> str:
    """reportlab Paragraph parses mini-HTML; escape any text that isn't ours."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def brief(group_id: str, compare_to: str = MARKET, target: str | None = None) -> dict:
    """Numbers and text for the carrier push-back brief."""
    a = analysis(group_id, compare_to=compare_to)
    g, b, bm = a["group"], a["breakdown"], a["benchmark"]
    kind = "requested" if bm["requested"] else "approved"
    target = target or (f"{bm['reference_pct']:.1f}% (the market median)" if bm["compare_to"] == MARKET
                        else f"{bm['reference_pct']:.1f}% (your filed average)")
    if bm["compare_to"] == MARKET:
        context = (f"For plan year 2027, Pennsylvania small-group carriers {kind} a median increase "
                   f"of {bm['reference_pct']:.1f}% (range {bm['range_low_pct']:.1f}% to "
                   f"{bm['range_high_pct']:.1f}% across carriers).")
    else:
        context = (f"{bm['against']}'s filing for plan year 2027 {kind} an average increase of "
                   f"{bm['reference_pct']:.1f}%, with products ranging {bm['range_low_pct']:.1f}% "
                   f"to {bm['range_high_pct']:.1f}%.")
    paragraphs = [
        f"{g['name']}'s renewal raises monthly premium from ${b['current_monthly']:,.0f} to "
        f"${b['renewal_monthly']:,.0f}, an increase of {b['total_pct']:.1f}%. We separated the "
        f"increase into its two drivers:",
        f"With aging removed, the base-rate change for this group is "
        f"{b['pure_rate_change_pct']:.1f}%. {context} Filed rates may be reduced before approval.",
        f"We ask that you review the base-rate change for this group, share the factors behind the "
        f"portion above the benchmark, and consider revising it toward {target}.",
    ]
    return {
        "group": g, "breakdown": b, "benchmark": bm, "target": target,
        "subject": f"{g['name']} · group renewal effective {_long_date(g['renewal_date'])}",
        "title": "Request to review the base-rate change",
        "table": [
            {"label": "Employees moving into older age bands", "amount": b["aging"],
             "pct": b["aging_pct"]},
            {"label": "Base-rate change", "amount": b["rate"], "pct": b["rate_pct"]},
            {"label": "Total increase", "amount": b["total_change"], "pct": b["total_pct"]},
        ],
        "paragraphs": paragraphs,
        "source": ("ratereview.healthcare.gov, Pennsylvania, small group, plan year 2027, retrieved "
                   "Sep 24, 2026. Aging calculated with the ACA federal default age curve."),
    }


def brief_pdf(data: dict, sender: str = "[Broker name], [Agency]",
              recipient: str = "[Carrier account manager]") -> bytes:
    import io

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["Normal"], fontSize=10.5, leading=15)
    small = ParagraphStyle("s", parent=body, fontSize=8.5, leading=12, textColor=colors.grey)
    rows = [[r["label"], f"{'+' if r['amount'] >= 0 else ''}${r['amount']:,.0f}/mo",
             f"{r['pct']:.1f}%"] for r in data["table"]]
    t = Table(rows, colWidths=[300, 110, 70], hAlign="LEFT")
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 10), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                           ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#E3E7E1")),
                           ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                           ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F2F7F3")),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    p = data["paragraphs"]
    story = [Paragraph(f"<b>To:</b> {escape_markup(recipient)}<br/><b>From:</b> "
                       f"{escape_markup(sender)}<br/><b>Re:</b> {escape_markup(data['subject'])}",
                       body), Spacer(1, 14),
             Paragraph(f"<b>{data['title']}</b>", ParagraphStyle("h", parent=body, fontSize=14,
                                                                 leading=18)), Spacer(1, 8),
             Paragraph(escape_markup(p[0]), body), Spacer(1, 8), t, Spacer(1, 10),
             Paragraph(escape_markup(p[1]), body), Spacer(1, 8),
             Paragraph(escape_markup(p[2]), body), Spacer(1, 14),
             Paragraph(f"Thank you,<br/>{escape_markup(sender)}", body), Spacer(1, 18),
             Paragraph("Source: " + data["source"], small)]
    SimpleDocTemplate(buf, pagesize=letter, leftMargin=64, rightMargin=64, topMargin=60,
                      bottomMargin=60, title=data["title"]).build(story)
    return buf.getvalue()
