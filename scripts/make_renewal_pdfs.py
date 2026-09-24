"""Generate a sample renewal notice PDF for each sample group.

Run:  python scripts/make_renewal_pdfs.py
Writes data/<group id>/renewal_notice.pdf. Carrier, rates and people are fictional.
"""

import sys
from datetime import date
from decimal import Decimal as D
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from renewal_advisor.census import generate_group  # noqa: E402

RENEWAL_DATE = date(2027, 1, 1)
# Illustrative increases per plan (a real renewal rarely moves every plan equally).
# Chosen to sit inside the range PA carriers requested for 2027 (3.7% to 28.4%,
# median 14.5%); see data/rate_filings/.
INCREASES = {"plan_gold": D("1.19"), "plan_silver": D("1.18"), "plan_bronze": D("1.165")}


def make_pdf(group, out: Path) -> dict[str, D]:
    styles = getSampleStyleSheet()
    carrier = group.plans[0].carrier
    new_rates = {p.id: (p.base_rate_21 * INCREASES[p.id]).quantize(D("0.01")) for p in group.plans}
    rows = [["Plan ID", "Plan name", "Current rate (age 21)", "Renewal rate (age 21)", "Change"]]
    for p in group.plans:
        chg = (new_rates[p.id] / p.base_rate_21 - 1) * 100
        rows.append([p.id, p.plan_name, f"${p.base_rate_21:,.2f}", f"${new_rates[p.id]:,.2f}",
                     f"+{chg:.1f}%"])
    table = Table(rows, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story = [
        Paragraph(f"{carrier} Small Group Renewal Notice", styles["Title"]),
        Paragraph(f"Employer: {group.name}", styles["Normal"]),
        Paragraph(f"Group ID: {group.id}", styles["Normal"]),
        Paragraph(f"Renewal effective date: {RENEWAL_DATE:%B} {RENEWAL_DATE.day}, "
                  f"{RENEWAL_DATE.year}", styles["Normal"]),
        Spacer(1, 12),
        Paragraph("Monthly rates shown for a 21-year-old. Member premiums are the rate "
                  "multiplied by the ACA age factor for each covered person.", styles["Normal"]),
        Spacer(1, 8),
        table,
        Spacer(1, 12),
        Paragraph("SAMPLE DOCUMENT - fictional carrier and rates, for demonstration only.",
                  styles["Italic"]),
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(out), pagesize=letter).build(story)
    return new_rates


if __name__ == "__main__":
    for size, seed in [(12, 1), (30, 2), (45, 3)]:
        g = generate_group(size, seed)
        path = ROOT / "data" / g.id / "renewal_notice.pdf"
        make_pdf(g, path)
        print("wrote", path.relative_to(ROOT))
