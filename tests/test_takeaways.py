"""The Bottom line sentences must always match the computed numbers."""
import pytest

from renewal_advisor.filings import load_filings
from renewal_advisor.service import SAMPLES, analysis


def _by_id(a):
    return {t["id"]: t["text"] for t in a["takeaways"]}


@pytest.mark.parametrize("gid", list(SAMPLES))
def test_three_takeaways_quote_the_payload(gid):
    a = analysis(gid)
    t = _by_id(a)
    assert list(t) == ["why", "fair", "do"]
    b, bm, best = a["breakdown"], a["benchmark"], a["options"][0]
    assert f"+{b['total_pct']:.1f}%" in t["why"]
    assert f"{b['aging_pct']:.1f} points" in t["why"]
    assert f"{b['rate_pct']:.1f} points" in t["why"]
    assert f"{bm['group_rate_pct']:.1f}%" in t["fair"]
    assert f"{bm['gap_pct']:.1f} points above" in t["fair"]
    assert f"{best['employer_change_pct']:+.1f}%" in t["do"]
    assert t["do"].startswith("If the carrier won't lower the rate,")


def test_linden_reads_as_expected():
    t = _by_id(analysis("grp_30_2"))
    assert "2.8 points is employees aging" in t["why"]
    assert "3.6 points above the PA median of 14.5%" in t["fair"]
    assert "move everyone to Bronze HSA 6000" in t["do"]  # plan name keeps its case
    assert "only 2 of 27 employees pay more (at most $3.44/month)" in t["do"]
    assert "21 of 27 employees move to a $6,000 deductible" in t["do"]


def test_no_feasible_option_names_the_missed_goals():
    a = analysis("grp_30_2", max_deductible=3500)
    assert not a["search"]["any_feasible"]
    do = _by_id(a)["do"]
    assert do.startswith("No plan and contribution mix meets every goal.")
    assert f"{a['options'][0]['employer_change_pct']:+.1f}% against a +5% budget" in do
    assert do.endswith("Negotiating the rate down is the main lever.")


def test_rate_below_carrier_average_does_not_suggest_push_back():
    top = max(load_filings(), key=lambda f: f.requested_pct)
    a = analysis("grp_30_2", compare_to=top.company)
    assert a["benchmark"]["verdict"] == "within"
    t = _by_id(a)
    assert "points below" in t["fair"] and "leverage is limited" in t["fair"]
    assert t["do"].startswith("The best option is to")


def test_above_every_product_in_carrier_filing():
    low = min(load_filings(), key=lambda f: f.range_high_pct)
    a = analysis("grp_30_2", compare_to=low.company)
    assert a["benchmark"]["verdict"] == "above_range"
    assert "above every product" in _by_id(a)["fair"]


def test_singular_employee_grammar():
    do = _by_id(analysis("grp_45_3"))["do"]
    assert "only 1 of 40 employees pays more" in do


def test_summary_headline():
    assert analysis("grp_30_2")["summary"] == (
        "Push back first: the rate change is 3.6 points above the market.")
    assert analysis("grp_30_2", max_deductible=3500)["summary"].endswith(
        "no plan change meets the goals at this rate.")
