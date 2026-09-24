from datetime import date
from decimal import Decimal as D

import pytest

from renewal_advisor.census import generate_group
from renewal_advisor.contributions import uniform_percentage_strategy
from renewal_advisor.models import Group, Member, Plan
from renewal_advisor.scenarios import (Scenario, accept_renewal, baseline, compare, evaluate,
                                       move_all_to, with_strategy)

START, RENEWAL = date(2026, 1, 1), date(2027, 1, 1)
PCT70 = uniform_percentage_strategy(70)
NEW_RATES = {"gold": D("560"), "silver": D("440")}


def two_person_group():
    def m(mid, dob, plan):
        return Member(id=mid, first_name=mid, last_name="X", dob=dob, employer="g",
                      hire_date=date(2020, 1, 1), state="PA", zip_code="19103",
                      enrolled_plan=plan)
    plans = [Plan(id="gold", plan_name="Gold", carrier="A", state="PA", base_rate_21=D("500")),
             Plan(id="silver", plan_name="Silver", carrier="A", state="PA", base_rate_21=D("400"))]
    members = [m("A", date(1976, 6, 1), "gold"),    # 49 -> 50
               m("B", date(1996, 6, 1), "silver")]  # 29 -> 30
    return Group(id="g", name="G", state="PA", plan_year_start=START,
                 members=members, plans=plans)


def test_baseline_hand_computed():
    r = evaluate(two_person_group(), baseline(two_person_group(), PCT70)).by_member()
    assert (r["A"].total, r["A"].employer, r["A"].employee) == (D("853.00"), D("597.10"), D("255.90"))
    assert (r["B"].total, r["B"].employer, r["B"].employee) == (D("447.60"), D("313.32"), D("134.28"))


def test_accept_renewal_hand_computed():
    g = two_person_group()
    base = evaluate(g, baseline(g, PCT70))
    ren = evaluate(g, accept_renewal(NEW_RATES, PCT70, RENEWAL))
    r = ren.by_member()
    assert (r["A"].total, r["A"].employer, r["A"].employee) == (D("1000.16"), D("700.11"), D("300.05"))
    assert (r["B"].total, r["B"].employer, r["B"].employee) == (D("499.40"), D("349.58"), D("149.82"))
    c = compare(base, ren)
    assert base.employer_annual == D("10925.04")
    assert c.employer_annual == D("12596.28")
    assert c.employer_annual_change == D("1671.24")
    assert c.employer_change_pct == D("15.30")
    assert c.employees_paying_more == 2
    assert c.max_employee_increase == D("44.15")  # A: 300.05 - 255.90


def test_move_all_to_silver():
    g = two_person_group()
    r = evaluate(g, move_all_to("silver", g, NEW_RATES, PCT70, RENEWAL)).by_member()
    assert r["A"].plan_id == "silver"
    assert (r["A"].total, r["A"].employer, r["A"].employee) == (D("785.84"), D("550.09"), D("235.75"))


def test_lower_contribution():
    g = two_person_group()
    s = with_strategy(accept_renewal(NEW_RATES, PCT70, RENEWAL),
                      uniform_percentage_strategy(60), "Renewal at 60%")
    r = evaluate(g, s).by_member()
    assert (r["A"].employer, r["A"].employee) == (D("600.10"), D("400.06"))
    assert (r["B"].employer, r["B"].employee) == (D("299.64"), D("199.76"))


def test_alternate_carrier_plan_via_extra_plans():
    g = two_person_group()
    alt = Plan(id="alt_silver", plan_name="Alt Silver", carrier="B", state="PA",
               base_rate_21=D("420"))
    rates = {**NEW_RATES, "alt_silver": D("420")}
    r = evaluate(g, move_all_to("alt_silver", g, rates, PCT70, RENEWAL, (alt,))).by_member()
    assert r["B"].total == D("476.70")  # 420 x 1.135


def test_unknown_plan_raises():
    g = two_person_group()
    bad = Scenario("bad", NEW_RATES, PCT70, RENEWAL, {"gold": "nope"})
    with pytest.raises(KeyError):
        evaluate(g, bad)


def test_invariants_on_generated_groups():
    for size, seed in [(12, 1), (30, 2), (45, 3)]:
        g = generate_group(size, seed)
        base = evaluate(g, baseline(g, PCT70))
        assert compare(base, base).employer_annual_change == 0
        new = {p.id: (p.base_rate_21 * D("1.13")).quantize(D("0.01")) for p in g.plans}
        for s in [accept_renewal(new, PCT70, RENEWAL),
                  move_all_to("plan_bronze", g, new, PCT70, RENEWAL)]:
            res = evaluate(g, s)
            assert all(r.employer + r.employee == r.total for r in res.rows)
            assert res.employer_monthly + res.employee_monthly == res.total_monthly
            assert len(res.rows) == len(g.enrolled_members)
