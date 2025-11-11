# core/boundary/pin_serializers.py
from rest_framework import serializers
from core.models import Request, ClaimReport
# class for requestCreateSerializer
class RequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Request
        fields = ["service_type", "appointment_date", "appointment_time",
                  "pickup_location", "service_location", "description"]

class RequestListSerializer(serializers.ModelSerializer):
    shortlist_count = serializers.IntegerField(read_only=True, default=0)
    class Meta:
        model = Request
        fields = ["id", "status", "service_type", "appointment_date", "appointment_time",
                  "pickup_location", "service_location", "created_at", "completed_at","shortlist_count",]
# class OtpCodeSerializer
class OtpCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6)

class ProfileUpdateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6)
    # fields user wants to update
    fields = serializers.DictField(child=serializers.CharField(), allow_empty=False)


class PasswordChangeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(min_length=8, write_only=True)

class ClaimReportSerializer(serializers.ModelSerializer):
    request_id = serializers.CharField(source="request.id", read_only=True)

    class Meta:
        model = ClaimReport
        fields = ["id", "request_id", "category", "expense_date", "amount",
                  "payment_method", "description", "status", "created_at"]

class DisputeSerializer(serializers.Serializer):
    reason = serializers.CharField()
    comment = serializers.CharField(required=False, allow_blank=True)


class PinClaimSerializer(serializers.ModelSerializer):
    receipt_url = serializers.SerializerMethodField()

    class Meta:
        model = ClaimReport
        fields = [
            "id", "request", "request_id", "cv", "cv_id",
            "category", "expense_date", "amount", "payment_method",
            "description", "status",
            # keep receipt name if you want, optional:
            "receipt", 
            # new absolute URL for the UI:
            "receipt_url",
            "created_at",
        ]

    def get_receipt_url(self, obj):
        if not obj.receipt:
            return None
        request = self.context.get("request")
        url = obj.receipt.url  # e.g. /media/receipts/xxx.jpg
        return request.build_absolute_uri(url) if request else url

