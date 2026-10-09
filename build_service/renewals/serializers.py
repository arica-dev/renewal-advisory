"""DRF serializers: the contract for everything that enters the service.

The same PacketSerializer validates the layout parser's output, Claude's tool
output, and the reviewed packet the browser sends back, so a malformed value
fails loudly at the boundary instead of flowing into the rate math.
"""

from __future__ import annotations

import json
from datetime import timedelta

from rest_framework import serializers

STATUSES = ["renews", "renamed", "replaced", "modified", "discontinued", "new"]
METHODS = ["auto", "layout", "claude"]


class SourceSerializer(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, required=False)
    bbox = serializers.ListField(child=serializers.FloatField(), min_length=4, max_length=4,
                                 required=False, allow_null=True)
    sheet = serializers.CharField(required=False, allow_blank=True)
    cell = serializers.RegexField(r"^[A-Z]{1,3}\d{1,6}$", required=False)
    text = serializers.CharField(required=False, allow_blank=True)
    verified = serializers.BooleanField(required=False)
    edited = serializers.BooleanField(required=False)


class RateSerializer(serializers.Serializer):
    label = serializers.RegexField(r"^\d{1,2}(\s*[-–]\s*\d{1,2}|\s*\+)?$", max_length=8)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    source = SourceSerializer(required=False)


class PlanSerializer(serializers.Serializer):
    key = serializers.SlugField(required=False)
    current_plan_name = serializers.CharField(max_length=120)
    current_code = serializers.CharField(max_length=60, required=False, allow_blank=True)
    renewal_plan_name = serializers.CharField(max_length=120)
    renewal_code = serializers.CharField(max_length=60, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=STATUSES)
    notes = serializers.CharField(required=False, allow_blank=True)
    deductible = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    oop_max = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    current_rate_21 = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    renewal_rate_21 = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    rates = RateSerializer(many=True, allow_empty=False)
    sources = serializers.DictField(child=SourceSerializer(), required=False)
    clasp_plan_id = serializers.CharField(required=False, allow_blank=True)


class PacketSerializer(serializers.Serializer):
    carrier = serializers.CharField(max_length=120, required=False, allow_blank=True, allow_null=True)
    employer_name = serializers.CharField(max_length=160, required=False, allow_blank=True, allow_null=True)
    group_number = serializers.CharField(max_length=60, required=False, allow_blank=True, allow_null=True)
    effective_date = serializers.DateField()
    state = serializers.RegexField(r"^[A-Za-z]{2}$", required=False, allow_null=True)
    plans = PlanSerializer(many=True, allow_empty=False)


def clean_packet(raw: dict) -> dict:
    """Validate an extracted packet and return plain JSON-ready data."""
    s = PacketSerializer(data=raw)
    s.is_valid(raise_exception=True)
    return json.loads(json.dumps(s.data))


class ExtractRequestSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=METHODS, default="auto")


class UploadSerializer(ExtractRequestSerializer):
    file = serializers.FileField()

    def validate_file(self, f):
        from django.conf import settings

        if f.size > settings.MAX_UPLOAD_BYTES:
            raise serializers.ValidationError("Packets must be 5 MB or smaller.")
        if not f.name.lower().endswith((".pdf", ".xlsx")):
            raise serializers.ValidationError("Upload a PDF or an .xlsx spreadsheet.")
        return f


class OpenEnrollmentSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    enrollment_type = serializers.ChoiceField(choices=["passive", "active"], default="passive")


class ContributionSerializer(serializers.Serializer):
    employee_only_pct = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)
    dependent_pct = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)


class GenerateSerializer(serializers.Serializer):
    packet = PacketSerializer()
    contribution = ContributionSerializer(required=False)
    kept = serializers.ListField(child=serializers.CharField(max_length=120), required=False, default=list)
    open_enrollment = OpenEnrollmentSerializer()

    def validate(self, attrs):
        oe, eff = attrs["open_enrollment"], attrs["packet"]["effective_date"]
        if not oe["start_date"] < oe["end_date"] < eff:
            raise serializers.ValidationError(
                {"open_enrollment": "Open enrollment must start before it ends, and end before "
                                    f"the renewal effective date ({eff:%b %-d, %Y})."})
        if eff - oe["start_date"] > timedelta(days=120):
            raise serializers.ValidationError(
                {"open_enrollment": "Open enrollment should start within 120 days of renewal."})
        return attrs
