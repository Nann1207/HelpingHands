# core/boundary/pin_serializers.py
from rest_framework import serializers
from core.models import Request, ClaimReport

class RequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Request
        fields = ["service_type", "appointment_date", "appointment_time",
                  "pickup_location", "service_location", "description"]

class RequestListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Request
        fields = ["id", "status", "service_type", "appointment_date", "appointment_time",
                  "pickup_location", "service_location", "created_at", "completed_at"]

class OtpCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6)

class ProfileUpdateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6)
    # fields user wants to update
    fields = serializers.DictField(child=serializers.CharField(), allow_empty=False)

class ClaimReportSerializer(serializers.ModelSerializer):
    request_id = serializers.CharField(source="request.id", read_only=True)

    class Meta:
        model = ClaimReport
        fields = ["id", "request_id", "category", "expense_date", "amount",
                  "payment_method", "description", "status", "created_at"]

class DisputeSerializer(serializers.Serializer):
    reason = serializers.CharField()
    comment = serializers.CharField(required=False, allow_blank=True)
