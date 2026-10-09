"""Renewal Build: every planted problem is caught, nothing else blocks, and the
generated Clasp requests are valid and carry the right numbers."""

from __future__ import annotations

import copy
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from renewal_advisor import service
from renewals.services import extract as ex
from renewals.services.clasp_requests import validate
from renewals.services.layout_parser import parse_pdf, parse_xlsx
from renewals.views import process

SAMPLES = ["grp_30_2", "grp_45_3", "grp_12_1"]


def truth(gid: str) -> dict:
    return json.loads((settings.PACKETS_DIR / f"{gid}.truth.json").read_text())


def packet_bytes(gid: str) -> tuple[bytes, str]:
    t = truth(gid)
    path = settings.PACKETS_DIR / f"{gid}.{t['format']}"
    return path.read_bytes(), path.name


@pytest.fixture
def api():
    return APIClient()


@pytest.mark.parametrize("gid", SAMPLES)
def test_layout_parser_reads_every_value(gid):
    t = truth(gid)
    data, name = packet_bytes(gid)
    p = (parse_xlsx if name.endswith(".xlsx") else parse_pdf)(data)
    assert p["effective_date"] == t["effective_date"]
    assert p["group_number"] == t["group_number"]
    for got, want in zip(p["plans"], t["plans"]):
        assert got["renewal_plan_name"] == want["renewal_plan_name"]
        assert got["status"] == want["status"]
        assert {r["label"]: r["amount"] for r in got["rates"]} == dict(want["rates"])


@pytest.mark.parametrize("gid", SAMPLES)
def test_checks_catch_exactly_the_planted_problems(gid):
    result = process(*packet_bytes(gid), method="layout")
    blockers = {f["kind"] for f in result["checks"] if f["severity"] == "blocker"}
    planted = {p["kind"] for p in truth(gid)["planted_problems"]}
    assert blockers == planted - {"current_rate"}  # a current-rate difference is a review item
    if "current_rate" in planted:
        assert any(f["kind"] == "current_rate" for f in result["checks"])


def test_keying_error_is_explained_and_fixed_to_the_curve():
    result = process(*packet_bytes("grp_30_2"), method="layout")
    flag = next(f for f in result["checks"] if f["kind"] == "age_curve")
    planted = truth("grp_30_2")["planted_problems"][0]
    assert flag["label"] == planted["age"] and flag["fix"]["amount"] == planted["correct"]
    assert "swapped" in flag["detail"]


def test_every_rate_has_a_source_on_the_page():
    result = process(*packet_bytes("grp_30_2"), method="layout")
    for plan in result["packet"]["plans"]:
        for r in plan["rates"]:
            assert r["source"]["verified"] and len(r["source"]["bbox"]) == 4 and r["source"]["page"] >= 2
    assert len(result["pages"]) == 4 and result["pages"][0]["image"].startswith("data:image/png")


def test_build_preview_matches_the_renewal_advisor():
    """The build feeds the Advisor engine: Linden's numbers agree to the cent."""
    result = process(*packet_bytes("grp_30_2"), method="layout")
    advisor = service.analysis("grp_30_2")["breakdown"]
    assert result["preview"]["total_pct"] == advisor["total_pct"]
    assert result["preview"]["pure_rate_pct"] == advisor["pure_rate_change_pct"]


def _resolved_body(result: dict) -> dict:
    packet = copy.deepcopy(result["packet"])
    kept = []
    for f in result["checks"]:
        fix = f.get("fix") or {}
        plan = next((p for p in packet["plans"] if p["key"] == f["plan"]), None)
        if fix.get("action") == "set_rate":
            rate = next(r for r in plan["rates"] if r["label"] == fix["label"])
            rate["amount"], rate["source"]["edited"] = fix["amount"], True
        elif fix.get("action") == "add_rate":
            plan["rates"].append({"label": fix["label"], "amount": fix["amount"], "source": {"edited": True}})
        elif fix.get("action") == "set_effective_date":
            packet["effective_date"] = fix["value"]
        elif f["severity"] == "review":
            kept.append(f["id"])
    oe = dict(result["open_enrollment"])
    return {"packet": packet, "kept": kept, "open_enrollment": oe}


def test_generate_is_refused_until_problems_are_resolved(api):
    result = process(*packet_bytes("grp_30_2"), method="layout")
    r = api.post("/api/build/requests", {"packet": result["packet"], "kept": [],
                                         "open_enrollment": result["open_enrollment"]}, format="json")
    assert r.status_code == 409
    assert {f["kind"] for f in r.json()["unresolved"]} == {"age_curve", "mapping"}


def test_missing_rate_cannot_be_kept(api):
    result = process(*packet_bytes("grp_45_3"), method="layout")
    body = {"packet": result["packet"], "kept": [f["id"] for f in result["checks"]],
            "open_enrollment": result["open_enrollment"]}
    r = api.post("/api/build/requests", body, format="json")
    assert r.status_code == 409 and r.json()["unresolved"][0]["kind"] == "missing_age"


@pytest.mark.parametrize("gid", SAMPLES)
def test_resolved_packet_generates_valid_clasp_requests(api, gid):
    result = process(*packet_bytes(gid), method="layout")
    r = api.post("/api/build/requests", _resolved_body(result), format="json")
    assert r.status_code == 200, r.json()
    out = r.json()
    assert out["valid"] and out["headers"]["Clasp-Version"] == "2026-04-24"
    ops = [q["operation"] for q in out["requests"]]
    assert ops.count("plan_create") == 3 and ops[-1] == "open_enrollment_window_create"
    t = truth(gid)
    for q in out["requests"]:
        if q["operation"] == "plan_premiums_create":
            ages = [int(row["age"]) for row in q["body"]]
            assert ages == list(range(65))
    # Premiums carry the true renewal rates (planted errors corrected).
    gold = next(q for q in out["requests"] if q["operation"] == "plan_premiums_create")
    want21 = Decimal(t["plans"][0]["renewal_rate_21"])
    assert Decimal(next(row["amount"] for row in gold["body"] if row["age"] == "21")) == want21
    window = out["requests"][-1]["body"]
    assert window["enrollment_type"] == "passive" and len(window["plans"]) == 3
    assert {k for k in window["metadata"] if k.startswith("maps_to.")} == {
        "maps_to.plan_gold", "maps_to.plan_silver", "maps_to.plan_bronze"}


def test_schema_validation_catches_bad_bodies():
    assert validate("plan_premiums_create", [{"age": "21", "amount": "419.40"}]) == []
    errs = validate("plan_premiums_create", [{"age": "121", "amount": "4o0.00", "colour": "red"}])
    assert len(errs) == 3
    assert validate("open_enrollment_window_create", {"employer": "e", "start_date": "2026-11-16"})


def test_open_enrollment_must_end_before_renewal(api):
    result = process(*packet_bytes("grp_30_2"), method="layout")
    body = _resolved_body(result)
    body["open_enrollment"]["end_date"] = "2027-01-15"
    r = api.post("/api/build/requests", body, format="json")
    assert r.status_code == 400 and "open_enrollment" in r.json()


def test_claude_output_is_grounded_against_the_document():
    """A rate the model reports that isn't printed where it says gets flagged."""
    data, name = packet_bytes("grp_30_2")
    raw = parse_pdf(data)
    for plan in raw["plans"]:
        plan.pop("sources", None)
        for r in plan["rates"]:
            r["source"] = {"page": r["source"]["page"], "text": r["source"]["text"]}
    raw["plans"][0]["rates"][10]["amount"] = "999.99"  # not in the document
    fake = SimpleNamespace(messages=SimpleNamespace(
        create=lambda **kw: SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=raw)])))
    result = process(data, name, method="claude", client=fake)
    assert result["extractor"]["method"] == "claude"
    unverified = [f for f in result["checks"] if f["kind"] == "unverified"]
    assert len(unverified) == 1 and unverified[0]["plan"] == "gold_ppo_1500"
    located = [r for r in result["packet"]["plans"][1]["rates"] if r["source"].get("bbox")]
    assert len(located) == len(result["packet"]["plans"][1]["rates"])


def test_upload_endpoint(api):
    data, name = packet_bytes("grp_12_1")
    from django.core.files.uploadedfile import SimpleUploadedFile

    r = api.post("/api/build/extract", {"file": SimpleUploadedFile(name, data), "method": "layout"},
                 format="multipart")
    assert r.status_code == 200 and r.json()["context"]["group_id"] == "grp_12_1"
    r = api.post("/api/build/extract", {"file": SimpleUploadedFile("x.txt", b"hi")}, format="multipart")
    assert r.status_code == 400


def test_unknown_layout_without_claude_explains_what_is_needed(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from reportlab.pdfgen import canvas
    import io

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "Some other carrier's renewal")
    c.save()
    with pytest.raises(ex.ExtractionError, match="ANTHROPIC_API_KEY"):
        process(buf.getvalue(), "other.pdf", method="auto")
