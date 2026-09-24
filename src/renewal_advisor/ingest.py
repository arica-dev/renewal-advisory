"""Getting data in: renewal notice PDFs and census CSV uploads.

Renewal PDFs: `parse_renewal_pdf` reads the sample carrier layout
(scripts/make_renewal_pdfs.py) with pdfplumber. Real carriers all use
different layouts; `extract_with_claude` is the fallback for those. It asks
Claude for JSON in the RenewalNotice schema and validates it with Pydantic,
so a bad extraction fails loudly instead of flowing into the math. The broker
should still review extracted rates before using them (the app shows them in
an editable table).
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import BinaryIO

from pydantic import BaseModel, Field

from .models import Dependent, Group, Member, Plan


class RenewalRate(BaseModel):
    plan_id: str
    plan_name: str
    current_rate_21: Decimal = Field(gt=0)
    renewal_rate_21: Decimal = Field(gt=0)

    @property
    def change_pct(self) -> Decimal:
        return ((self.renewal_rate_21 / self.current_rate_21 - 1) * 100).quantize(Decimal("0.01"))


class RenewalNotice(BaseModel):
    carrier: str
    group_id: str | None = None
    effective_date: date
    rates: list[RenewalRate]

    def renewal_rates(self) -> dict[str, Decimal]:
        return {r.plan_id: r.renewal_rate_21 for r in self.rates}


class ExtractionError(ValueError):
    pass


_MONEY = re.compile(r"\$?\s*([0-9][0-9,]*\.[0-9]{2})")


def _money(s: str) -> Decimal:
    m = _MONEY.search(s or "")
    if not m:
        raise ExtractionError(f"No dollar amount in {s!r}")
    try:
        return Decimal(m.group(1).replace(",", ""))
    except InvalidOperation as e:  # pragma: no cover
        raise ExtractionError(str(e)) from e


def parse_renewal_pdf(source: str | Path | BinaryIO) -> RenewalNotice:
    """Parse the sample carrier layout. Raises ExtractionError if it doesn't fit."""
    import pdfplumber

    with pdfplumber.open(source) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        tables = [t for page in pdf.pages for t in page.extract_tables()]

    carrier = re.search(r"^(.+?)\s+Small Group Renewal Notice", text, re.M)
    eff = re.search(r"Renewal effective date:\s*([A-Za-z]+ \d{1,2}, \d{4})", text)
    gid = re.search(r"Group ID:\s*(\S+)", text)
    if not (carrier and eff):
        raise ExtractionError("Layout not recognised (missing carrier or effective date)")

    rates: list[RenewalRate] = []
    for table in tables:
        header = [(c or "").strip().lower() for c in table[0]]
        if not header or "plan id" not in header[0]:
            continue
        for row in table[1:]:
            if not row or not row[0] or not (row[0] or "").strip():
                continue
            rates.append(RenewalRate(plan_id=row[0].strip(), plan_name=(row[1] or "").strip(),
                                     current_rate_21=_money(row[2]),
                                     renewal_rate_21=_money(row[3])))
    if not rates:
        raise ExtractionError("No rate table found")

    return RenewalNotice(carrier=carrier.group(1).strip(),
                         group_id=gid.group(1) if gid else None,
                         effective_date=datetime.strptime(eff.group(1), "%B %d, %Y").date(),
                         rates=rates)


def extract_with_claude(pdf_bytes: bytes, model: str = "claude-sonnet-4-5") -> RenewalNotice:
    """Fallback for unfamiliar layouts. Needs ANTHROPIC_API_KEY and the
    `anthropic` package. The model name is a placeholder: set it to a
    current model. Not covered by tests (needs a live key)."""
    import base64

    import anthropic

    client = anthropic.Anthropic()
    schema = json.dumps(RenewalNotice.model_json_schema())
    msg = client.messages.create(
        model=model, max_tokens=2000,
        messages=[{"role": "user", "content": [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                            "data": base64.b64encode(pdf_bytes).decode()}},
            {"type": "text", "text": (
                "Extract this small-group health renewal notice as JSON matching this schema. "
                "Rates are monthly premiums for a 21-year-old. Return only JSON, no prose.\n"
                + schema)},
        ]}])
    raw = msg.content[0].text.strip().removeprefix("```json").removesuffix("```").strip()
    return RenewalNotice.model_validate_json(raw)


def check_against_group(notice: RenewalNotice, group: Group) -> list[str]:
    """Human-readable problems to show the broker before using the rates."""
    problems = []
    known = {p.id: p for p in group.plans}
    for r in notice.rates:
        p = known.get(r.plan_id)
        if p is None:
            problems.append(f"{r.plan_id} is on the renewal but not in the group's plans")
        elif p.base_rate_21 != r.current_rate_21:
            problems.append(f"{r.plan_id}: renewal says current rate ${r.current_rate_21}, "
                            f"group has ${p.base_rate_21}")
    missing = set(known) - {r.plan_id for r in notice.rates}
    problems += [f"{m} has no renewal rate" for m in sorted(missing)]
    if notice.group_id and notice.group_id != group.id:
        problems.append(f"Renewal is for group {notice.group_id}, not {group.id}")
    return problems


def census_from_csv(members_csv: str | bytes, dependents_csv: str | bytes | None,
                    group_id: str, name: str, state: str, plan_year_start: date,
                    plans: list[Plan]) -> Group:
    """Build a Group from uploaded CSVs (same columns as census.write_census)."""
    def text(x):
        return x.decode() if isinstance(x, bytes) else x

    deps: dict[str, list[Dependent]] = {}
    if dependents_csv:
        for row in csv.DictReader(io.StringIO(text(dependents_csv))):
            member = row.pop("member")
            deps.setdefault(member, []).append(Dependent(**row))
    members = []
    for row in csv.DictReader(io.StringIO(text(members_csv))):
        row["enrolled_plan"] = row.get("enrolled_plan") or None
        members.append(Member(**row, dependents=deps.get(row["id"], [])))
    return Group(id=group_id, name=name, state=state, plan_year_start=plan_year_start,
                 members=members, plans=plans)
