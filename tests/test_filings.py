from decimal import Decimal as D

from renewal_advisor.filings import against_carrier, against_market, load_filings, market_summary


def test_pa_file_loads_all_16_filings():
    f = load_filings()
    assert len(f) == 16
    assert {x.status for x in f} == {"Submission Filed"}
    assert all(not x.is_final for x in f)
    assert all(x.range_low_pct <= x.range_high_pct for x in f)
    assert all(x.range_low_pct <= x.requested_pct <= x.range_high_pct for x in f)


def test_market_summary_hand_checked():
    # sorted requested: ... 13.96, 14.98 ... -> median of 16 = (13.96 + 14.98) / 2
    m = market_summary(load_filings())
    assert m.count == 16
    assert m.median_pct == D("14.47")
    assert (m.low_pct, m.high_pct) == (D("3.74"), D("28.38"))
    assert not m.all_final


def test_carrier_verdicts():
    hca = next(x for x in load_filings() if x.company == "Highmark Coverage Advantage Inc.")
    assert against_carrier(D("15.00"), hca).verdict == "above_range"    # range tops at 13.59
    assert against_carrier(D("12.00"), hca).verdict == "above_average"  # avg 11.54
    b = against_carrier(D("10.00"), hca)
    assert b.verdict == "within" and b.gap_pct == D("-1.54") and b.requested


def test_market_verdicts():
    f = load_filings()
    assert against_market(D("18.00"), f).verdict == "above_average"
    assert against_market(D("30.00"), f).verdict == "above_range"
    assert against_market(D("14.47"), f).verdict == "within"
