"""API contract tests (FastAPI TestClient)."""
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.index import app  # noqa: E402

client = TestClient(app)


def test_groups_list():
    r = client.get("/api/groups")
    assert r.status_code == 200
    gs = r.json()
    assert {g["id"] for g in gs} == {"grp_12_1", "grp_30_2", "grp_45_3"}
    linden = next(g for g in gs if g["id"] == "grp_30_2")
    assert linden["name"] == "Linden Architecture"
    assert linden["current_monthly"] == 38572.86 and linden["renewal_monthly"] == 46822.01
    assert linden["verdict"] == "above_average" and linden["market_median_pct"] == 14.47


def test_analysis_defaults_match_engine():
    a = client.get("/api/groups/grp_30_2/analysis").json()
    b = a["breakdown"]
    assert round(b["aging"] + b["rate"], 2) == b["total_change"]
    assert a["benchmark"]["verdict"] == "above_average"
    assert a["today"]["employer_annual"] == 324012.0
    top = a["options"][0]
    assert top["feasible"] and top["employer_change_pct"] <= 5
    assert top["max_employee_increase"] <= 100
    assert len(top["employees"]) == a["group"]["enrolled"]
    assert top["moved_to_higher_deductible"] == 21 and top["target_deductible"] == 6000.0


def test_analysis_with_carrier_and_deductible_cap():
    a = client.get("/api/groups/grp_30_2/analysis",
                   params={"compare_to": "Highmark Coverage Advantage Inc.",
                           "max_deductible": 3500}).json()
    assert a["benchmark"]["verdict"] == "above_range"
    assert not a["search"]["any_feasible"]
    assert all("Bronze" not in o["design"] for o in a["options"])


def test_not_found_and_validation():
    assert client.get("/api/groups/nope/analysis").status_code == 404
    assert client.get("/api/groups/grp_30_2/analysis", params={"compare_to": "Nobody"}).status_code == 404
    assert client.get("/api/groups/grp_30_2/analysis", params={"objective": "x"}).status_code == 422


def test_brief_json_and_pdf():
    j = client.get("/api/groups/grp_30_2/brief").json()
    assert "14.5%" in j["paragraphs"][1] and "18.0%" in j["paragraphs"][1]
    assert j["subject"].endswith("January 1, 2027")
    r = client.get("/api/groups/grp_30_2/brief.pdf", params={"sender": "A <b>&", "target": "12%"})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


def test_filings():
    f = client.get("/api/filings").json()
    assert len(f["carriers"]) == 16 and f["median_pct"] == 14.47 and f["requested_only"]
