"""Generate the three sample groups and print a renewal breakdown for each.

Run:  python scripts/demo.py
"""

import sys
from datetime import date
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from renewal_advisor.census import generate_group, write_census  # noqa: E402
from renewal_advisor.contributions import uniform_percentage_strategy  # noqa: E402
from renewal_advisor.filings import load_filings, market_summary  # noqa: E402
from renewal_advisor.recommender import Goals, recommend  # noqa: E402
from renewal_advisor.renewal import benchmark, break_down_renewal  # noqa: E402
from renewal_advisor.scenarios import (accept_renewal, baseline, compare,  # noqa: E402
                                       evaluate, move_all_to, with_strategy)

RENEWAL_DATE = date(2027, 1, 1)
RATE_INCREASE = D("1.18")          # illustrative carrier base-rate change
FILED_AVG_PCT = market_summary(load_filings()).median_pct  # PA small group 2027, requested

for size, seed in [(12, 1), (30, 2), (45, 3)]:
    g = generate_group(size, seed)
    write_census(g, ROOT / "data" / g.id)
    new_rates = {p.id: (p.base_rate_21 * RATE_INCREASE).quantize(D("0.01")) for p in g.plans}
    b = break_down_renewal(g, new_rates, RENEWAL_DATE)
    bm = benchmark(b, FILED_AVG_PCT)
    print(f"\n{g.name}: {len(g.enrolled_members)} enrolled")
    print(f"  Monthly premium  {b.current_monthly:>10,}  ->  {b.renewal_monthly:>10,}"
          f"   ({b.total_pct:+}%)")
    print(f"  From aging       {b.aging_effect:>10,}   ({b.aging_pct:+}% of current)")
    print(f"  From rate change {b.rate_effect:>10,}   ({b.rate_pct:+}% of current)")
    print(f"  Pure rate change {b.pure_rate_change_pct:+}% vs filed avg {bm.filed_avg_pct:+}%"
          f"  -> gap {bm.gap_pct:+} pts{'  [push back]' if bm.flag else ''}")

    # Scenario comparison (employer pays 70% of every tier today)
    pct70 = uniform_percentage_strategy(70)
    base = evaluate(g, baseline(g, pct70))
    options = [
        accept_renewal(new_rates, pct70, RENEWAL_DATE),
        move_all_to("plan_silver", g, new_rates, pct70, RENEWAL_DATE),
        with_strategy(accept_renewal(new_rates, pct70, RENEWAL_DATE),
                      uniform_percentage_strategy(60), "Accept renewal, employer 60%"),
    ]
    print(f"  {'Option':<34}{'Employer/yr':>13}{'Change':>9}{'Paying more':>13}{'Max +/mo':>10}")
    print(f"  {'Today':<34}{base.employer_annual:>13,}")
    for s in options:
        c = compare(base, evaluate(g, s))
        print(f"  {c.name:<34}{c.employer_annual:>13,}{c.employer_change_pct:>+8}%"
              f"{c.employees_paying_more:>13}{c.max_employee_increase:>10,}")

    # Recommender: employer increase <= 5%, no one paying > $100/mo more.
    # Run twice: any plan allowed, then deductible capped at $3,500.
    labels = {"employer_increase_pct": "employer goal by {:.2f} pts",
              "employee_monthly_increase": "employee cap by ${:.2f}/mo"}
    for title, goals in [
        ("any plan", Goals(max_employer_increase_pct=D(5), max_employee_monthly_increase=D(100))),
        ("deductible <= $3,500", Goals(max_employer_increase_pct=D(5),
                                        max_employee_monthly_increase=D(100),
                                        max_deductible=D(3500))),
    ]:
        rec = recommend(g, pct70, new_rates, RENEWAL_DATE, goals)
        print(f"  Recommended, {title} ({rec.evaluated} options searched):")
        for i, c in enumerate(rec.top, 1):
            cm = c.comparison
            worst = (f"max +${cm.max_employee_increase}/mo" if cm.employees_paying_more
                     else "no one pays more")
            tag = "meets goals" if c.feasible else "misses " + ", ".join(
                labels[k].format(v) for k, v in c.violations.items())
            print(f"   {i}. {c.label}\n      employer {cm.employer_change_pct:+}%/yr, "
                  f"{cm.employees_paying_more} paying more, {worst}  [{tag}]")
