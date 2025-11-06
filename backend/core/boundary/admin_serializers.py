from rest_framework import serializers
from core.models import FlaggedRequest, Request

class FlaggedRequestSerializer(serializers.ModelSerializer):
    request_id = serializers.CharField(source="request.id", read_only=True)
    csr_name = serializers.CharField(source="csr.name", read_only=True)
    resolved_by_name = serializers.CharField(source="resolved_by.name", read_only=True)

    class Meta:
        model = FlaggedRequest
        fields = [
            "id", "request_id", "flag_type", "csr_name",
            "reason", "created_at", "resolved",
            "resolved_by_name", "resolved_at", "resolution_notes",
        ]

class RequestSummarySerializer(serializers.ModelSerializer):
    pin_id = serializers.CharField(source="pin.id", read_only=True)
    pin_name = serializers.CharField(source="pin.name", read_only=True)
    cv_id = serializers.CharField(source="cv.id", read_only=True)
    cv_name = serializers.CharField(source="cv.name", read_only=True)

    class Meta:
        model = Request
        fields = [
            "id", "status", "service_type",
            "appointment_date", "appointment_time",
            "pin_id", "pin_name", "cv_id", "cv_name",
            "created_at",
        ]