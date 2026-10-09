"""HTTP endpoints (Django REST Framework), mounted at /api/build/.

GET  health                      is Claude configured?
GET  samples                     the sample carrier packets
GET  samples/<id>/file           download a sample packet
POST samples/<id>/extract        read + check a sample packet
POST extract                     read + check an uploaded packet (multipart)
POST requests                    approved packet -> Clasp API requests
"""

from __future__ import annotations

import copy
import json
from datetime import date, timedelta

from django.conf import settings
from django.http import FileResponse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ExtractRequestSerializer, GenerateSerializer, UploadSerializer, clean_packet
from .services import extract as ex
from .services.checks import run_checks, unresolved
from .services.clasp_requests import build_requests
from .services.context import clasp_context
from .services.money import ExtractionError
from .services.preview import renewal_preview

SAMPLE_BLURBS = {
    "grp_30_2": "One plan renamed, one rate keyed wrong.",
    "grp_45_3": "A plan replaced by a successor, one age missing.",
    "grp_12_1": "Effective date and a current rate disagree with Clasp.",
}


def _sample_path(sample_id: str):
    for ext in ("pdf", "xlsx"):
        p = settings.PACKETS_DIR / f"{sample_id}.{ext}"
        if p.exists():
            return p
    return None


def default_open_enrollment(effective: str) -> dict:
    eff = date.fromisoformat(effective)
    return {"start_date": (eff - timedelta(days=46)).isoformat(),
            "end_date": (eff - timedelta(days=31)).isoformat(), "enrollment_type": "passive"}


def process(data: bytes, filename: str, method: str, client=None) -> dict:
    fmt = ex.detect_format(filename, data)
    raw, extractor = ex.read(data, fmt, method, client=client)
    try:
        packet = clean_packet(raw)
    except ValidationError as e:
        raise ExtractionError(f"The extracted packet failed validation: {json.dumps(e.detail)[:400]}") from e
    for plan in packet["plans"]:
        plan["key"] = plan.get("key") or ex.plan_key(plan["renewal_plan_name"])
        plan["rates"].sort(key=lambda r: ex.first_age(r["label"]))
    ex.ground(packet, data, fmt)
    ctx = clasp_context(packet.get("group_number"))
    checks = run_checks(packet, ctx)
    return {
        "filename": filename, "format": fmt, "extractor": extractor, "packet": packet,
        "context": ctx, "checks": checks, "preview": renewal_preview(packet, ctx),
        "open_enrollment": default_open_enrollment((ctx or packet)["renewal_date" if ctx else "effective_date"]),
        "pages": ex.pdf_pages(data) if fmt == "pdf" else [],
        "sheets": ex.xlsx_sheets(data) if fmt == "xlsx" else [],
    }


def _extraction_error(e: Exception) -> Response:
    return Response({"detail": str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


class HealthView(APIView):
    def get(self, request):
        return Response({"ok": True, "claude_available": ex.claude_available(),
                         "model": settings.ANTHROPIC_MODEL if ex.claude_available() else None,
                         "clasp_api_version": settings.CLASP_API_VERSION})


class SampleListView(APIView):
    def get(self, request):
        out = []
        order = list(SAMPLE_BLURBS)
        truths = sorted(settings.PACKETS_DIR.glob("*.truth.json"),
                        key=lambda t: order.index(t.name.split(".")[0]) if t.name.split(".")[0] in order else 99)
        for truth in truths:
            spec = json.loads(truth.read_text())
            path = _sample_path(spec["group_id"])
            if path is None:
                continue
            out.append({"id": spec["group_id"], "employer": spec["employer"], "carrier": spec["carrier"],
                        "format": spec["format"], "filename": path.name,
                        "effective_date": spec["effective_date"], "plans": len(spec["plans"]),
                        "blurb": SAMPLE_BLURBS.get(spec["group_id"], "")})
        return Response(out)


class SampleFileView(APIView):
    def get(self, request, sample_id: str):
        path = _sample_path(sample_id)
        if path is None:
            return Response({"detail": "Not found"}, status=404)
        return FileResponse(path.open("rb"), filename=path.name)


class SampleExtractView(APIView):
    def post(self, request, sample_id: str):
        path = _sample_path(sample_id)
        if path is None:
            return Response({"detail": "Not found"}, status=404)
        s = ExtractRequestSerializer(data=request.data or request.query_params)
        s.is_valid(raise_exception=True)
        try:
            return Response(process(path.read_bytes(), path.name, s.validated_data["method"]))
        except ExtractionError as e:
            return _extraction_error(e)


class UploadExtractView(APIView):
    def post(self, request):
        s = UploadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        f = s.validated_data["file"]
        try:
            return Response(process(f.read(), f.name, s.validated_data["method"]))
        except ExtractionError as e:
            return _extraction_error(e)


class GenerateRequestsView(APIView):
    def post(self, request):
        s = GenerateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        packet = json.loads(json.dumps(GenerateSerializer(s.validated_data).data["packet"]))
        for plan in packet["plans"]:
            plan["key"] = plan.get("key") or ex.plan_key(plan["renewal_plan_name"])
        ctx = clasp_context(packet.get("group_number"))
        if ctx is None:
            return Response({"detail": "This packet isn't matched to a Clasp group, so there's "
                                       "nothing to build into."}, status=404)
        checks = run_checks(copy.deepcopy(packet), ctx)
        blocking = unresolved(checks, set(s.validated_data["kept"]))
        if blocking:
            return Response({"detail": "Resolve these before generating requests.",
                             "unresolved": blocking}, status=status.HTTP_409_CONFLICT)
        run_checks(packet, ctx)  # sets clasp_plan_id on each plan
        oe = {k: (v.isoformat() if hasattr(v, "isoformat") else v)
              for k, v in s.validated_data["open_enrollment"].items()}
        return Response({**build_requests(packet, ctx, oe), "preview": renewal_preview(packet, ctx)})
