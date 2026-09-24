"""Renewal Advisor - Streamlit front-end.

Run:  streamlit run app.py
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from renewal_advisor.census import generate_group  # noqa: E402
from renewal_advisor.ingest import (ExtractionError, RenewalNotice, RenewalRate,  # noqa: E402
                                    census_from_csv, check_against_group, parse_renewal_pdf)
from renewal_advisor.recommender import Goals, recommend, scenario_for, tiered_strategy  # noqa: E402
from renewal_advisor.filings import (SOURCE_URL, against_carrier, against_market,  # noqa: E402
                                     load_filings)
from renewal_advisor.renewal import break_down_renewal  # noqa: E402
from renewal_advisor.scenarios import accept_renewal, baseline, compare, evaluate  # noqa: E402

SERIES = "#2a78d6"      # categorical slot 1 (reference palette)
MUTED = "#8a8984"       # reference lines
SAMPLES = {"Sample Co (12 employees)": (12, 1), "Sample Co (30 employees)": (30, 2),
           "Sample Co (45 employees)": (45, 3)}
GOAL_LABELS = {"employer_increase_pct": "employer goal by {:.2f} pts",
               "employee_monthly_increase": "employee cap by ${:,.2f}/mo"}

st.set_page_config(page_title="Renewal Advisor", layout="wide")


def money(x, decimals=0) -> str:
    return f"${x:,.{decimals}f}"


# ---------------------------------------------------------------- sidebar ---
with st.sidebar:
    st.header("1. Group")
    source = st.radio("Census", [*SAMPLES, "Upload CSVs"], index=1, label_visibility="collapsed")
    sample_group = generate_group(*SAMPLES.get(source, (30, 2)))
    if source == "Upload CSVs":
        members_file = st.file_uploader("members.csv", type="csv")
        deps_file = st.file_uploader("dependents.csv (optional)", type="csv")
        start = st.date_input("Current plan year start", date(2026, 1, 1))
        st.caption("Uses the sample plan lineup (Gold / Silver / Bronze).")
        if not members_file:
            st.info("Upload members.csv to continue.")
            st.stop()
        group = census_from_csv(members_file.getvalue(),
                                deps_file.getvalue() if deps_file else None,
                                "uploaded", "Uploaded group", "PA", start, sample_group.plans)
    else:
        group = sample_group

    st.header("2. Renewal")
    pdf = st.file_uploader("Renewal notice PDF", type="pdf",
                           help="Leave empty to use the sample group's renewal notice.")
    notice: RenewalNotice | None = None
    try:
        if pdf is not None:
            notice = parse_renewal_pdf(pdf)
        elif source in SAMPLES:
            notice = parse_renewal_pdf(ROOT / "data" / group.id / "renewal_notice.pdf")
    except ExtractionError as e:
        st.warning(f"Couldn't read that layout ({e}). Enter the renewal rates below.")
    if notice is None:
        notice = RenewalNotice(carrier="Unknown", effective_date=date(2027, 1, 1), rates=[
            RenewalRate(plan_id=p.id, plan_name=p.plan_name, current_rate_21=p.base_rate_21,
                        renewal_rate_21=p.base_rate_21) for p in group.plans])

    st.caption("Review the extracted rates (monthly, age 21). You can edit them.")
    edited = st.data_editor(
        pd.DataFrame([{"plan_id": r.plan_id, "Plan": r.plan_name.split()[0],
                       "Current": float(r.current_rate_21), "Renewal": float(r.renewal_rate_21)}
                      for r in notice.rates]),
        column_config={"plan_id": None,
                       "Current": st.column_config.NumberColumn(format="$%.2f", disabled=True),
                       "Renewal": st.column_config.NumberColumn(format="$%.2f", min_value=1.0)},
        hide_index=True, width="stretch", key=f"rates_{group.id}_{pdf.name if pdf else 'sample'}")
    renewal_rates = {row.plan_id: D(str(row.Renewal)).quantize(D("0.01"))
                     for row in edited.itertuples()}
    renewal_date = st.date_input("Renewal effective date", notice.effective_date)
    for problem in check_against_group(notice, group) if pdf is not None else []:
        st.warning(problem)

    filings = load_filings()
    MARKET = "PA small-group market (median of 16 carriers)"
    compare_to = st.selectbox(
        "Compare with 2027 rate filings", [MARKET, *sorted(f.company for f in filings)],
        help="Requested increases filed for 1/1/2027, from ratereview.healthcare.gov "
             "(retrieved Sep 24, 2026). Pick the renewing carrier if you know it.")

    st.header("3. Today's contribution")
    c1, c2 = st.columns(2)
    cur_emp = c1.number_input("Employee-only %", 0, 100, 70, 5)
    cur_dep = c2.number_input("With dependents %", 0, 100, 70, 5)

    st.header("4. Goals")
    max_er = st.number_input("Max employer increase (%)", value=5.0, step=1.0)
    max_ee = st.number_input("Max monthly increase for any employee ($)", value=100, step=25)
    min_c = st.number_input("Carrier minimum, employee-only (%)", 0, 100, 50, 5)
    ded = st.selectbox("Highest deductible allowed", ["Any", 1500, 3500, 6000], index=0,
                       key="max_deductible")
    objective = st.radio("Within the goals, prefer", ["protect_employees", "lowest_employer_cost"],
                         format_func={"protect_employees": "Lowest cost to employees",
                                      "lowest_employer_cost": "Lowest cost to employer"}.get)

# ---------------------------------------------------------------- compute ---
current = tiered_strategy(D(cur_emp), D(cur_dep))
goals = Goals(max_employer_increase_pct=D(str(max_er)),
              max_employee_monthly_increase=D(max_ee), min_employee_only_pct=D(min_c),
              max_deductible=None if ded == "Any" else D(ded))
breakdown = break_down_renewal(group, renewal_rates, renewal_date)
rate_pct = breakdown.pure_rate_change_pct
if compare_to == MARKET:
    bench = against_market(rate_pct, filings)
else:
    bench = against_carrier(rate_pct, next(f for f in filings if f.company == compare_to))
base_res = evaluate(group, baseline(group, current))
accept = compare(base_res, evaluate(group, accept_renewal(renewal_rates, current, renewal_date)))
with st.spinner("Searching options..."):
    rec = recommend(group, current, renewal_rates, renewal_date, goals, objective=objective)

# ------------------------------------------------------------------- main ---
st.title("Renewal Advisor")
st.caption(f"{group.name} · {len(group.enrolled_members)} enrolled · {notice.carrier} renewal "
           f"effective {renewal_date:%b %d, %Y} · synthetic data for demonstration")

st.subheader("What's driving the increase")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Monthly premium today", money(breakdown.current_monthly))
m2.metric("At renewal", money(breakdown.renewal_monthly), f"{breakdown.total_pct:+}%",
          delta_color="inverse")
m3.metric("From employees aging", money(breakdown.aging_effect), f"{breakdown.aging_pct:+} pts",
          delta_color="off")
m4.metric("From the carrier's rate change", money(breakdown.rate_effect),
          f"{breakdown.rate_pct:+} pts", delta_color="off")

kind = "requested" if bench.requested else "approved"
range_txt = (f"carriers' averages ranged {bench.range_low_pct}% to {bench.range_high_pct}%"
             if compare_to == MARKET else
             f"its products ranged {bench.range_low_pct}% to {bench.range_high_pct}%")
ref_txt = (f"{bench.reference_pct}% median {kind} increase across Pennsylvania small-group "
           f"carriers" if compare_to == MARKET else
           f"{bench.reference_pct}% average {kind} increase in {bench.against}'s filing")
if bench.verdict == "above_range":
    st.info(f"**Strong case to push back.** With aging removed, this renewal raises rates "
            f"**{bench.group_rate_pct}%**. That's above the {ref_txt} and above the top of the "
            f"range ({range_txt}).", icon=":material/balance:")
elif bench.verdict == "above_average":
    st.info(f"**Room to push back.** With aging removed, this renewal raises rates "
            f"**{bench.group_rate_pct}%**, **{bench.gap_pct} points** above the {ref_txt} "
            f"({range_txt}).", icon=":material/balance:")
else:
    st.info(f"With aging removed, this renewal raises rates **{bench.group_rate_pct}%**, at or "
            f"below the {ref_txt} ({range_txt}).", icon=":material/check_circle:")
st.caption(f"Source: [ratereview.healthcare.gov]({SOURCE_URL}), Pennsylvania small group, plan "
           f"year 2027, retrieved Sep 24, 2026. Filed rates are {kind}; regulators often approve "
           f"less. A filed average is a benchmark, not proof about one group's renewal.")

st.subheader("Recommended options")
if rec.feasible:
    st.caption(f"Searched {rec.evaluated:,} combinations of plan design and contribution.")
else:
    st.warning("No option meets every goal. Showing the closest misses, plus how far each one "
               "is off. Negotiating the rate down, or relaxing a goal, would open up options.",
               icon=":material/warning:")

rows = []
for i, c in enumerate(rec.top, 1):
    cm = c.comparison
    rows.append({
        "#": i, "Option": c.design,
        "Employer pays": f"{c.employee_only_pct}% / {c.dependent_tiers_pct}%",
        "Meets goals": "Yes" if c.feasible else "No",
        "Employer / yr": float(cm.employer_annual), "Change": float(cm.employer_change_pct),
        "Paying more": cm.employees_paying_more,
        "Max +/mo": float(max(cm.max_employee_increase, D(0))),
        "Missed by": "; ".join(GOAL_LABELS[k].format(v) for k, v in c.violations.items()) or "-",
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
    "Employer pays": st.column_config.TextColumn(help="Employee-only / tiers with dependents"),
    "Employer / yr": st.column_config.NumberColumn(format="$%,.0f"),
    "Change": st.column_config.NumberColumn("vs today", format="%+.2f%%"),
    "Max +/mo": st.column_config.NumberColumn(help="Largest monthly increase for any employee",
                                              format="$%,.2f"),
})

# Employer annual cost: today, accept renewal, recommended options (one series).
labels = ["Today", "Accept renewal"] + [f"#{i}" for i in range(1, len(rec.top) + 1)]
values = [float(base_res.employer_annual), float(accept.employer_annual)] + \
         [float(c.comparison.employer_annual) for c in rec.top]
hover = ["Current plans and contribution", "Same plans and contribution at renewal rates"] + \
        [c.label for c in rec.top]
budget = float(base_res.employer_annual * (1 + goals.max_employer_increase_pct / 100))
fig = go.Figure(go.Bar(
    x=labels, y=values, marker=dict(color=SERIES, cornerradius=4), width=0.5,
    text=[money(v) for v in values], textposition="inside", insidetextanchor="end",
    textfont=dict(color="white"),
    customdata=hover, hovertemplate="<b>%{x}</b><br>%{customdata}<br>%{y:$,.0f} / yr<extra></extra>"))
fig.add_hline(y=budget, line=dict(color=MUTED, dash="dash", width=1.5), layer="below")
fig.update_layout(title=f"Employer cost per year (dashed line = budget, today "
                        f"+{goals.max_employer_increase_pct}%)", height=380, margin=dict(t=60, b=20, l=10, r=10),
                  yaxis=dict(tickformat="$,.0f", gridcolor="rgba(128,128,128,0.15)",
                             range=[0, max(values + [budget]) * 1.15]),
                  xaxis=dict(showgrid=False, type="category"), bargap=0.4, showlegend=False)
st.plotly_chart(fig, width="stretch")

st.subheader("Effect on each employee")
choices = {"Accept renewal": accept_renewal(renewal_rates, current, renewal_date)}
for i, c in enumerate(rec.top, 1):
    choices[f"#{i} {c.label}"] = scenario_for(c, group, renewal_rates, renewal_date)
pick = st.selectbox("Option", list(choices), index=1 if rec.top else 0)
new_res = evaluate(group, choices[pick])
plan_names = {p.id: p.plan_name for p in group.plans}
before, after = base_res.by_member(), new_res.by_member()
emp = pd.DataFrame([{
    "Employee": before[k].name, "Coverage": before[k].coverage_type.value.replace("_", " + "),
    "Plan today": plan_names[before[k].plan_id], "Plan at renewal": plan_names[after[k].plan_id],
    "Pays today / mo": float(before[k].employee), "Pays at renewal / mo": float(after[k].employee),
    "Change / mo": float(after[k].employee - before[k].employee),
} for k in before]).sort_values("Change / mo", ascending=False)
st.dataframe(emp, hide_index=True, width="stretch", column_config={
    "Pays today / mo": st.column_config.NumberColumn(format="$%,.2f"),
    "Pays at renewal / mo": st.column_config.NumberColumn(format="$%,.2f"),
    "Change / mo": st.column_config.NumberColumn(format="%+.2f"),
})
st.caption("Premium share only. Moving to a plan with a higher deductible also raises what "
           "employees pay when they use care.")

with st.expander("How this works"):
    st.markdown(
        "- **Rating:** each covered person costs the plan's 21-year-old rate x the federal ACA "
        "age factor; only the three oldest children under 21 are charged.\n"
        "- **Breakdown:** *aging* = today's rates at next year's ages, minus today's premium. "
        "*Rate change* = the rest. The two add up exactly.\n"
        "- **Benchmark:** the rate change with aging removed, compared with a carrier's 2027 "
        "requested increase and product range, or with the state market median.\n"
        "- **Recommender:** tries every plan design (keep, or move everyone to one plan) x "
        "employer % for employee-only x employer % with dependents, in 5% steps, keeps those that "
        "meet the goals, and picks the best within each design.\n"
        "- All math is deterministic Python; field names follow Clasp's API.")
