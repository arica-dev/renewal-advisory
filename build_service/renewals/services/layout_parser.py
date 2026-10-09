"""Deterministic reader for one known carrier layout (the sample "Carrier A" packets).

Real carriers all lay renewals out differently, so this parser is the fast,
free path for a layout we have seen before; claude_extractor.py reads anything
else. Both return the same packet shape (see extract.py), and every value keeps
its source: a page and box in a PDF, or a sheet and cell in a spreadsheet.
"""

from __future__ import annotations

import io
import re

from .money import ExtractionError, money, parse_date

PLAN_CHANGE_HEADER = "current plan"
SUMMARY_HEADER = "renewal plan"


def _clean(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _bbox(cell) -> list[float] | None:
    return [round(v, 1) for v in cell] if cell else None


def parse_pdf(data: bytes) -> dict:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        if not pdf.pages:
            raise ExtractionError("The PDF has no pages")
        first = pdf.pages[0]
        text = first.extract_text() or ""
        head = {
            "carrier": re.search(r"^(.+?)\s+-\s+Small Group Renewal", text, re.M),
            "employer": re.search(r"Employer:\s*(.+)", text),
            "group": re.search(r"Group number:\s*(\S+)", text),
            "effective": re.search(r"Renewal effective:\s*(\S+)", text),
            "state": re.search(r"Rating state:\s*([A-Z]{2})", text),
        }
        if not (head["carrier"] and head["effective"]):
            raise ExtractionError("Layout not recognised (no carrier or effective date on page 1)")

        plans: dict[str, dict] = {}
        order: list[str] = []
        for table in first.find_tables():
            rows = table.extract()
            header = [_clean(c).lower() for c in rows[0]]
            if header and header[0] == PLAN_CHANGE_HEADER:
                for r in rows[1:]:
                    if not _clean(r[0]):
                        continue
                    name = _clean(r[2])
                    plans[name] = {
                        "current_plan_name": _clean(r[0]), "current_code": _clean(r[1]),
                        "renewal_plan_name": name, "renewal_code": _clean(r[3]),
                        "status": _clean(r[4]).lower(), "notes": _clean(r[5]),
                        "rates": [], "sources": {},
                    }
                    order.append(name)
            elif header and header[0] == SUMMARY_HEADER:
                for i, r in enumerate(rows[1:], start=1):
                    p = plans.get(_clean(r[0]))
                    if p is None:
                        continue
                    cells = table.rows[i].cells
                    p.update(deductible=str(money(r[1])), oop_max=str(money(r[2])),
                             current_rate_21=str(money(r[3])), renewal_rate_21=str(money(r[4])))
                    p["sources"].update(
                        current_rate_21={"page": 1, "bbox": _bbox(cells[3]), "text": _clean(r[3])},
                        renewal_rate_21={"page": 1, "bbox": _bbox(cells[4]), "text": _clean(r[4])})
        if not plans:
            raise ExtractionError("No plan table found on page 1")

        for page_no, page in enumerate(pdf.pages[1:], start=2):
            ptext = page.extract_text() or ""
            m = re.search(r"Age-banded monthly rates\s+-\s+(.+)", ptext)
            if not m or _clean(m.group(1)) not in plans:
                continue
            plan = plans[_clean(m.group(1))]
            for table in page.find_tables():
                rows = table.extract()
                if not rows or _clean(rows[0][0]).lower() != "age":
                    continue
                for i, r in enumerate(rows[1:], start=1):
                    cells = table.rows[i].cells
                    for c in range(0, len(r) - 1, 2):
                        label, amount = _clean(r[c]), _clean(r[c + 1])
                        if not label or not amount:
                            continue
                        plan["rates"].append({
                            "label": label, "amount": str(money(amount)),
                            "source": {"page": page_no, "bbox": _bbox(cells[c + 1]), "text": amount}})

    return {
        "carrier": _clean(head["carrier"].group(1)),
        "employer_name": _clean(head["employer"].group(1)) if head["employer"] else None,
        "group_number": head["group"].group(1) if head["group"] else None,
        "effective_date": parse_date(head["effective"].group(1)).isoformat(),
        "state": head["state"].group(1) if head["state"] else None,
        "plans": [plans[n] for n in order],
    }


def parse_xlsx(data: bytes) -> dict:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), data_only=True)
    if "Summary" not in wb.sheetnames:
        raise ExtractionError("Layout not recognised (no Summary sheet)")
    ws = wb["Summary"]
    fields: dict[str, str] = {}
    plans: dict[str, dict] = {}
    order: list[str] = []
    header_row = None
    for row in ws.iter_rows():
        values = [c.value for c in row]
        first = _clean(values[0]) if values else ""
        if header_row is None and first.lower() == PLAN_CHANGE_HEADER:
            header_row = [_clean(v).lower() for v in values]
            continue
        if header_row is not None:
            if not first:
                header_row = None if plans else header_row
                continue
            col = {h: i for i, h in enumerate(header_row)}
            name = _clean(values[col["renewal plan"]])
            cur_cell = row[col["current rate (21)"]]
            new_cell = row[col["renewal rate (21)"]]
            plans[name] = {
                "current_plan_name": first, "current_code": _clean(values[col["current code"]]),
                "renewal_plan_name": name, "renewal_code": _clean(values[col["renewal code"]]),
                "status": _clean(values[col["status"]]).lower(), "notes": _clean(values[col["notes"]]),
                "deductible": str(money(values[col["deductible"]])),
                "oop_max": str(money(values[col["oop max"]])),
                "current_rate_21": str(money(cur_cell.value)),
                "renewal_rate_21": str(money(new_cell.value)),
                "rates": [],
                "sources": {
                    "current_rate_21": {"sheet": "Summary", "cell": cur_cell.coordinate,
                                        "text": str(cur_cell.value)},
                    "renewal_rate_21": {"sheet": "Summary", "cell": new_cell.coordinate,
                                        "text": str(new_cell.value)}},
            }
            order.append(name)
        elif len(values) > 1 and first:
            fields[first.lower()] = _clean(values[1])
    if not plans or "renewal effective" not in fields:
        raise ExtractionError("Layout not recognised (no plan table or effective date)")

    for sheet in wb.worksheets[1:]:
        title = _clean(sheet["A1"].value)
        m = re.search(r"Age-banded monthly rates\s+-\s+(.+?)\s+\(", title)
        if not m or _clean(m.group(1)) not in plans:
            continue
        plan = plans[_clean(m.group(1))]
        for row in sheet.iter_rows(min_row=3):
            label, amount = row[0], row[1] if len(row) > 1 else None
            if amount is None or label.value is None or amount.value is None:
                continue
            try:
                value = money(amount.value)
            except ExtractionError:
                continue
            plan["rates"].append({"label": _clean(label.value), "amount": str(value),
                                  "source": {"sheet": sheet.title, "cell": amount.coordinate,
                                             "text": str(amount.value)}})

    carrier = re.search(r"^(.+?)\s+Small Group Renewal", _clean(ws["A1"].value))
    return {
        "carrier": carrier.group(1) if carrier else None,
        "employer_name": fields.get("employer"),
        "group_number": fields.get("group number"),
        "effective_date": parse_date(fields["renewal effective"]).isoformat(),
        "state": fields.get("rating state"),
        "plans": [plans[n] for n in order],
    }
