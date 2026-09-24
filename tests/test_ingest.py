import sys
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from make_renewal_pdfs import INCREASES, make_pdf  # noqa: E402
from renewal_advisor.census import generate_group, write_census  # noqa: E402
from renewal_advisor.ingest import (ExtractionError, census_from_csv, check_against_group,  # noqa: E402
                                    parse_renewal_pdf)


def test_pdf_round_trip(tmp_path):
    g = generate_group(30, 2)
    expected = make_pdf(g, tmp_path / "r.pdf")
    n = parse_renewal_pdf(tmp_path / "r.pdf")
    assert n.carrier == "Carrier A" and n.group_id == g.id
    assert n.effective_date == date(2027, 1, 1)
    assert n.renewal_rates() == expected
    assert {r.plan_id: r.current_rate_21 for r in n.rates} == {p.id: p.base_rate_21 for p in g.plans}
    assert check_against_group(n, g) == []


def test_change_pct():
    g = generate_group(12, 1)
    n = parse_renewal_pdf(ROOT / "data" / g.id / "renewal_notice.pdf")
    gold = next(r for r in n.rates if r.plan_id == "plan_gold")
    assert gold.change_pct == D("19.00") == (INCREASES["plan_gold"] - 1) * 100


def test_mismatch_is_reported(tmp_path):
    g = generate_group(30, 2)
    make_pdf(g, tmp_path / "r.pdf")
    other = generate_group(12, 1)
    problems = check_against_group(parse_renewal_pdf(tmp_path / "r.pdf"), other)
    assert any("not grp_12_1" in p for p in problems)


def test_unrecognised_pdf_raises(tmp_path):
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(tmp_path / "x.pdf"))
    c.drawString(72, 720, "Totally different layout")
    c.save()
    with pytest.raises(ExtractionError):
        parse_renewal_pdf(tmp_path / "x.pdf")


def test_census_upload_matches_generator(tmp_path):
    g = generate_group(45, 3)
    write_census(g, tmp_path)
    back = census_from_csv((tmp_path / "members.csv").read_bytes(),
                           (tmp_path / "dependents.csv").read_bytes(),
                           g.id, g.name, g.state, g.plan_year_start, g.plans)
    assert back == g
