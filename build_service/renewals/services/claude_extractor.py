"""Read any carrier's renewal packet with Claude.

Claude is asked to fill a strict tool schema (forced tool use), quoting the
exact printed text and page (or sheet and cell) for every rate. The output is
then validated by a DRF serializer, and every value is checked back against
the document by extract.ground() before anyone sees it. A rate Claude reports
that can't be found where it says it is gets flagged, not trusted.

Needs ANTHROPIC_API_KEY. Set ANTHROPIC_MODEL to choose the model.
"""

from __future__ import annotations

import base64
import io

from django.conf import settings

from .money import ExtractionError

SOURCE = {
    "type": "object",
    "description": "Where the value is printed. PDFs: page (1-based). Spreadsheets: sheet and cell (e.g. B12).",
    "properties": {"page": {"type": "integer"}, "sheet": {"type": "string"},
                   "cell": {"type": "string"},
                   "text": {"type": "string", "description": "The value exactly as printed, e.g. '$802.29'"}},
    "required": ["text"],
}

TOOL = {
    "name": "record_renewal_packet",
    "description": "Record everything in a small-group health insurance renewal packet.",
    "input_schema": {
        "type": "object",
        "properties": {
            "carrier": {"type": "string"},
            "employer_name": {"type": "string"},
            "group_number": {"type": "string"},
            "effective_date": {"type": "string", "description": "Renewal effective date, YYYY-MM-DD"},
            "state": {"type": "string", "description": "Two-letter rating state"},
            "plans": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "current_plan_name": {"type": "string"},
                    "current_code": {"type": "string"},
                    "renewal_plan_name": {"type": "string"},
                    "renewal_code": {"type": "string"},
                    "status": {"type": "string", "enum": ["renews", "renamed", "replaced", "modified",
                                                          "discontinued", "new"]},
                    "notes": {"type": "string"},
                    "deductible": {"type": "string"},
                    "oop_max": {"type": "string"},
                    "current_rate_21": {"type": "string"},
                    "renewal_rate_21": {"type": "string"},
                    "rates": {"type": "array", "description": "Every row of the plan's age-banded rate table, in order.",
                              "items": {"type": "object",
                                        "properties": {"label": {"type": "string", "description": "Age band as printed: '0-14', '37', '64+'"},
                                                       "amount": {"type": "string", "description": "Monthly rate, digits only, e.g. 802.29"},
                                                       "source": SOURCE},
                                        "required": ["label", "amount", "source"]}},
                },
                "required": ["current_plan_name", "renewal_plan_name", "status", "rates"],
            }},
        },
        "required": ["carrier", "effective_date", "plans"],
    },
}

INSTRUCTIONS = (
    "This is a carrier's small-group health insurance renewal packet. Record it with the "
    "record_renewal_packet tool. Rules:\n"
    "- Copy numbers exactly as printed. Never correct, round or infer a value; if a rate looks "
    "wrong, record it as printed (separate checks catch errors).\n"
    "- Include every row of every age-banded rate table, with the page (or sheet and cell) and the "
    "printed text for each rate.\n"
    "- Status: renews (same plan), renamed (new name, same benefits), replaced (discontinued and "
    "mapped to a successor), modified (benefits change), discontinued (no successor), new.\n"
    "- If a value isn't in the document, leave it out rather than guessing."
)


def _xlsx_as_text(data: bytes) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), data_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"=== Sheet: {ws.title} ===")
        for row in ws.iter_rows():
            cells = [f"{c.coordinate}={c.value}" for c in row if c.value is not None]
            if cells:
                out.append(" | ".join(cells))
    return "\n".join(out)


def extract(data: bytes, fmt: str, client=None) -> tuple[dict, str]:
    """Returns (raw packet dict, model). `client` is injectable for tests."""
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    if fmt == "pdf":
        doc = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                              "data": base64.b64encode(data).decode()}}
    else:
        doc = {"type": "text", "text": _xlsx_as_text(data)}
    model = settings.ANTHROPIC_MODEL
    msg = client.messages.create(
        model=model, max_tokens=16000, tools=[TOOL],
        tool_choice={"type": "tool", "name": TOOL["name"]},
        messages=[{"role": "user", "content": [doc, {"type": "text", "text": INSTRUCTIONS}]}])
    block = next((b for b in msg.content if getattr(b, "type", None) == "tool_use"), None)
    if block is None:
        raise ExtractionError("Claude did not return a packet")
    return dict(block.input), model
