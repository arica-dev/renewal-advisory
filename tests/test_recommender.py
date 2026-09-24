from datetime import date
from decimal import Decimal as D

from renewal_advisor.census import generate_group
from renewal_advisor.contributions import uniform_percentage_strategy
from renewal_advisor.recommender import Goals, recommend, tiered_strategy
from renewal_advisor.models import CoverageType
from renewal_advisor.scenarios import Scenario, baseline, compare, evaluate

RENEWAL = date(2027, 1, 1)
PCT70 = uniform_percentage_strategy(70)


def setup(size=30, seed=2):
    g = generate_group(size, seed)
    new = {p.id: (p.base_rate_21 * D("1.13")).quantize(D("0.01")) for p in g.plans}
    return g, new


def test_tiered_strategy_shape():
    s = tiered_strategy(D(80), D(40))
    assert s.employer_contribution[CoverageType.member].contribution == D(80)
    assert s.employer_contribution[CoverageType.member_family].contribution == D(40)


def test_recommendations_meet_every_goal():
    g, new = setup()
    goals = Goals(max_employer_increase_pct=D(5), max_employee_monthly_increase=D(150))
    rec = recommend(g, PCT70, new, RENEWAL, goals, step=10)
    assert rec.feasible and rec.top
    for c in [c for c in rec.top if c.feasible]:
        assert c.comparison.employer_change_pct <= 5
        assert c.comparison.max_employee_increase <= 150
        assert c.employee_only_pct >= 50
    assert len({c.design for c in rec.top}) == len(rec.top)  # distinct designs


def test_top_pick_is_cheapest_feasible_by_brute_force():
    g, new = setup(12, 1)
    goals = Goals(max_employer_increase_pct=D(8), max_employee_monthly_increase=D(200))
    rec = recommend(g, PCT70, new, RENEWAL, goals, step=10, objective="lowest_employer_cost")
    base = evaluate(g, baseline(g, PCT70))
    designs = [{}] + [{q.id: p.id for q in g.plans} for p in g.plans]
    best = None
    for mapping in designs:
        for e in range(50, 101, 10):
            for d in range(0, 101, 10):
                c = compare(base, evaluate(g, Scenario("x", new, tiered_strategy(D(e), D(d)),
                                                       RENEWAL, mapping)))
                if c.employer_change_pct <= 8 and c.max_employee_increase <= 200:
                    best = c.employer_annual if best is None else min(best, c.employer_annual)
    assert rec.top[0].comparison.employer_annual == best


def test_impossible_goals_return_closest_misses():
    g, new = setup()
    goals = Goals(max_employer_increase_pct=D(-40), max_employee_monthly_increase=D(0))
    rec = recommend(g, PCT70, new, RENEWAL, goals, step=25)
    assert not rec.feasible
    assert rec.top and all(c.violations for c in rec.top)


def test_min_contribution_respected():
    g, new = setup(12, 1)
    rec = recommend(g, PCT70, new, RENEWAL, Goals(min_employee_only_pct=D(75)), step=25)
    assert all(c.employee_only_pct >= 75 for c in rec.top)


def test_default_objective_minimises_employee_impact_by_brute_force():
    g, new = setup(12, 1)
    goals = Goals(max_employer_increase_pct=D(8), max_employee_monthly_increase=D(200))
    rec = recommend(g, PCT70, new, RENEWAL, goals, step=10)
    base = evaluate(g, baseline(g, PCT70))
    designs = [{}] + [{q.id: p.id for q in g.plans} for p in g.plans]
    best = None
    for mapping in designs:
        for e in range(50, 101, 10):
            for d in range(0, 101, 10):
                c = compare(base, evaluate(g, Scenario("x", new, tiered_strategy(D(e), D(d)),
                                                       RENEWAL, mapping)))
                if c.employer_change_pct <= 8 and c.max_employee_increase <= 200:
                    v = c.total_employee_monthly_change
                    best = v if best is None else min(best, v)
    assert rec.top[0].feasible
    assert rec.top[0].comparison.total_employee_monthly_change == best


def test_feasible_options_listed_before_misses():
    g, new = setup()
    goals = Goals(max_employer_increase_pct=D(5), max_employee_monthly_increase=D(100))
    rec = recommend(g, PCT70, new, RENEWAL, goals, step=10)
    flags = [c.feasible for c in rec.top]
    assert flags == sorted(flags, reverse=True)


def test_max_deductible_excludes_high_deductible_designs():
    g, new = setup()
    goals = Goals(max_employer_increase_pct=D(5), max_employee_monthly_increase=D(100),
                  max_deductible=D(3500))
    rec = recommend(g, PCT70, new, RENEWAL, goals, step=10)
    assert all("Bronze" not in c.design for c in rec.top)


def test_scenario_for_reproduces_candidate():
    from renewal_advisor.recommender import scenario_for
    g, new = setup()
    goals = Goals(max_employer_increase_pct=D(5), max_employee_monthly_increase=D(100))
    rec = recommend(g, PCT70, new, RENEWAL, goals, step=10)
    base = evaluate(g, baseline(g, PCT70))
    for c in rec.top:
        again = compare(base, evaluate(g, scenario_for(c, g, new, RENEWAL)))
        assert again.employer_annual == c.comparison.employer_annual
