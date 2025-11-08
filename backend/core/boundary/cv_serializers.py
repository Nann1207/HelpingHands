# core/Boundary/cv_serializers.py
from rest_framework import serializers
from core.models import Request, ClaimReport

class CvRequestListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Request
        fields = ["id", "status", "service_type", "appointment_date", "appointment_time",
                  "pickup_location", "service_location", "created_at", "completed_at"]

class ClaimCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimReport
        fields = ["category", "expense_date", "amount", "payment_method", "description", "receipt"]

class ClaimReportSerializer(serializers.ModelSerializer):
    request_id = serializers.CharField(source="request.id", read_only=True)
    class Meta:
        model = ClaimReport
        fields = ["id", "request_id", "category", "expense_date", "amount",
                  "payment_method", "description", "status", "created_at"]
