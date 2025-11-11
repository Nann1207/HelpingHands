from rest_framework import serializers
from core.models import FlaggedRequest, Request

#This is for flagged req serializer 
class FlaggedRequestSerializer(serializers.ModelSerializer):
    
    
    request_id = serializers.CharField(source="request.id", read_only=True)
    request_status = serializers.CharField(source="request.status", read_only=True)
    service_type = serializers.CharField(source="request.service_type", read_only=True)
    csr_name = serializers.CharField(source="csr.name", allow_null=True, default=None, read_only=True)

    
    reason = serializers.SerializerMethodField()

    class Meta:
        model = FlaggedRequest
        fields = [
            "id",
            "flag_type",
            "request_id",
            "request_status",
            "service_type",
            "csr_name",
            "reason",
            "created_at",
            "resolved",
            "resolved_at",
            "resolved_by",
            "resolution_notes",
            "resolution_outcome",
        ]

    def get_reason(self, obj):
        return getattr(obj, "reasonbycsr", "")

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
