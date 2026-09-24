"""HTTP API for the Renewal Advisor web app (FastAPI).

Local:   uvicorn api.index:app --reload --port 8000
Vercel:  deployed as a Python serverless function; Next.js rewrites /api/* here.
"""

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from renewal_advisor import service  # noqa: E402

app = FastAPI(title="Renewal Advisor API", docs_url="/api/docs", openapi_url="/api/openapi.json")


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except service.NotFound as e:
        raise HTTPException(status_code=404, detail=f"Not found: {e.args[0]}") from e


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/groups")
def groups():
    return service.list_groups()


@app.get("/api/filings")
def filings():
    return service.filings_payload()


@app.get("/api/groups/{group_id}/analysis")
def analysis(group_id: str,
             employee_only_pct: float = Query(70, ge=0, le=100),
             dependent_pct: float = Query(70, ge=0, le=100),
             max_employer_increase_pct: float = Query(5, ge=-50, le=100),
             max_employee_monthly_increase: float = Query(100, ge=0, le=5000),
             min_employee_only_pct: float = Query(50, ge=0, le=100),
             max_deductible: float | None = Query(None, ge=0),
             objective: str = Query("protect_employees",
                                    pattern="^(protect_employees|lowest_employer_cost)$"),
             compare_to: str = Query(service.MARKET, max_length=120)):
    return _guard(service.analysis, group_id, employee_only_pct=employee_only_pct,
                  dependent_pct=dependent_pct, max_employer_increase_pct=max_employer_increase_pct,
                  max_employee_monthly_increase=max_employee_monthly_increase,
                  min_employee_only_pct=min_employee_only_pct, max_deductible=max_deductible,
                  objective=objective, compare_to=compare_to)


@app.get("/api/groups/{group_id}/brief")
def brief(group_id: str, compare_to: str = Query(service.MARKET, max_length=120),
          target: str | None = Query(None, max_length=80)):
    return _guard(service.brief, group_id, compare_to, target)


@app.get("/api/groups/{group_id}/brief.pdf")
def brief_pdf(group_id: str, compare_to: str = Query(service.MARKET, max_length=120),
              target: str | None = Query(None, max_length=80),
              sender: str = Query("[Broker name], [Agency]", max_length=120),
              recipient: str = Query("[Carrier account manager]", max_length=120)):
    data = _guard(service.brief, group_id, compare_to, target)
    pdf = service.brief_pdf(data, sender=sender, recipient=recipient)
    name = data["group"]["name"].replace(" ", "-").lower()
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}-brief.pdf"'})

