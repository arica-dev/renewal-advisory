from datetime import date
from decimal import Decimal as D

import pytest

from renewal_advisor.age_curve import age_factor, age_on
from renewal_advisor.census import generate_group, read_census, write_census
from renewal_advisor.contributions import split_cost, uniform_percentage_strategy
from renewal_advisor.models import (ContributionRule, ContributionStrategy, ContributionType,
                                    CoverageType, Dependent, Group, Member, Plan)
from renewal_advisor.rating import member_premium, rate_member
from renewal_advisor.renewal import benchmark, break_down_renewal

AS_OF = date(2026, 1, 1)


def person(pid, dob, **kw):
    return Member(id=pid, first_name="A", last_name="B", dob=dob, employer="e",
                  hire_date=date(2020, 1, 1), state="PA", zip_code="19103", **kw)


def dep(pid, dob, rel):
    return Dependent(id=pid, first_name="C", last_name="B", dob=dob, member_relationship=rel)


# --- age curve ---------------------------------------------------------------

def test_age_curve_anchor_points():
    assert age_factor(0) == D("0.765")
    assert age_factor(14) == D("0.765")
    assert age_factor(21) == D("1.000")
    assert age_factor(40) == D("1.278")
    assert age_factor(64) == D("3.000")
    assert age_factor(80) == D("3.000")


def test_age_on_birthday_boundary():
    assert age_on(date(1986, 1, 1), AS_OF) == 40
    assert age_on(date(1986, 1, 2), AS_OF) == 39


def test_non_default_state_is_refused():
    with pytest.raises(NotImplementedError):
        age_factor(40, "NY")


# --- rating ------------------------------------------------------------------

def test_hand_computed_couple():
    # 40 -> 1.278, 38 -> 1.246 ; base 500
    m = person("m", date(1985, 6, 1), dependents=[dep("s", date(1987, 6, 1), "spouse")])
    assert member_premium(m, D("500"), AS_OF) == D("639.00") + D("623.00")
    assert m.coverage_type == CoverageType.member_spouse


def test_only_three_oldest_children_under_21_charged():
    kids = [dep(f"c{i}", date(2010 + i, 6, 1), "child") for i in range(5)]  # ages 15..11
    m = person("m", date(1980, 6, 1), dependents=kids)
    rated = {p.person_id: p for p in rate_member(m, D("400"), AS_OF)}
    assert [rated[f"c{i}"].charged for i in range(5)] == [True, True, True, False, False]
    assert m.coverage_type == CoverageType.member_children


def test_adult_child_does_not_use_up_under_21_slots():
    kids = [dep("adult", date(2003, 6, 1), "child")]  # 22
    kids += [dep(f"c{i}", date(2010 + i, 6, 1), "child") for i in range(4)]
    m = person("m", date(1975, 6, 1), dependents=kids)
    rated = {p.person_id: p for p in rate_member(m, D("400"), AS_OF)}
    assert rated["adult"].charged
    assert sum(rated[f"c{i}"].charged for i in range(4)) == 3


# --- renewal breakdown ----------------------------------------------------------

def single_member_group(dob):
    plan = Plan(id="p", plan_name="P", carrier="X", state="PA", base_rate_21=D("400"))
    m = person("m", dob, enrolled_plan="p")
    return Group(id="g", name="G", state="PA", plan_year_start=AS_OF, members=[m], plans=[plan])


def test_hand_computed_renewal_breakdown():
    # Age 49 at 2026-01-01, 50 at 2027-01-01. Base 400 -> 440 (+10%).
    g = single_member_group(date(1976, 6, 1))
    b = break_down_renewal(g, {"p": D("440")}, date(2027, 1, 1))
    assert b.current_monthly == D("682.40")   # 400 x 1.706
    assert b.renewal_monthly == D("785.84")   # 440 x 1.786
    assert b.aging_effect == D("32.00")       # 400 x (1.786 - 1.706)
    assert b.rate_effect == D("71.44")
    assert b.pure_rate_change_pct == D("10.00")


def test_breakdown_sums_exactly_on_generated_groups():
    for size, seed in [(12, 1), (30, 2), (45, 3)]:
        g = generate_group(size, seed)
        new = {p.id: (p.base_rate_21 * D("1.113")).quantize(D("0.01")) for p in g.plans}
        b = break_down_renewal(g, new, date(2027, 1, 1))
        assert b.aging_effect + b.rate_effect == b.total_change
        assert b.aging_effect >= 0


def test_no_rate_change_means_all_aging():
    g = generate_group(20, 7)
    same = {p.id: p.base_rate_21 for p in g.plans}
    b = break_down_renewal(g, same, date(2027, 1, 1))
    assert b.rate_effect == 0


def test_benchmark_flags_gap():
    g = single_member_group(date(1976, 6, 1))
    b = break_down_renewal(g, {"p": D("440")}, date(2027, 1, 1))
    bm = benchmark(b, D("7.5"))
    assert bm.gap_pct == D("2.50") and bm.flag


# --- contributions -------------------------------------------------------------

def test_percentage_split():
    s = split_cost(D("1262.00"), CoverageType.member_spouse, uniform_percentage_strategy(70))
    assert (s.employer, s.employee) == (D("883.40"), D("378.60"))


def test_flat_contribution_capped_at_premium_and_threshold():
    rule = ContributionRule(contribution_type=ContributionType.flat_employer_cost,
                            contribution=D("800"), monthly_max_threshold=D("600"))
    strat = ContributionStrategy(employer_contribution={ct: rule for ct in CoverageType})
    assert split_cost(D("1000"), CoverageType.member, strat).employer == D("600")
    assert split_cost(D("450"), CoverageType.member, strat).employer == D("450")


# --- census --------------------------------------------------------------------

def test_generator_is_deterministic_and_round_trips(tmp_path):
    a, b = generate_group(30, 2), generate_group(30, 2)
    assert a == b and len(a.members) == 30
    write_census(a, tmp_path)
    back = read_census(tmp_path, a.id, a.name, a.state, a.plan_year_start, a.plans)
    assert back.members == a.members
