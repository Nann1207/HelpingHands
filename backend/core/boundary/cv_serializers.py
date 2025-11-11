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
    receipt_url = serializers.SerializerMethodField()

    class Meta:
        model = ClaimReport
        fields = [
            "id", "request", "cv",
            "category", "expense_date", "amount",
            "payment_method", "description",
            "status", "created_at", "updated_at",
            "receipt_url",
        ]

    def get_receipt_url(self, obj):
        try:
            if obj.receipt:
                request = self.context.get("request")
                url = obj.receipt.url  
                return request.build_absolute_uri(url) if request else url
        except Exception:
            pass
        return None
