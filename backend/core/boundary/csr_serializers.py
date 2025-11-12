# core/Boundary/serializers_csr.py
"""
Serializers for CSR (Corporate Social Responsibility) features.
Used by csr_views to read/write Request, Shortlist, MatchQueue, Claim, and Notification data.
"""

from rest_framework import serializers
from core.models import ShortlistedRequest, Notification, MatchQueue, ClaimReport, CV


# ---------- BASIC READ MODELS ----------

class _SafeDict(dict):
    """Return None for missing keys so DRF fields treat them as empty."""

    def __missing__(self, key):
        return None


class RequestListSerializer(serializers.Serializer):
    """
    Lightweight serializer that mirrors the dict payloads returned by CSR controllers.
    Only `id` is required; every other field is optional because different UI
    widgets render different subsets of data.
    """

    id = serializers.CharField()
    service_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    category = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    status = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    appointment_date = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    appointment_time = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    pickup_location = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    service_location = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    shortlist_count = serializers.IntegerField(required=False, default=0)
    pin = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cv = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def to_representation(self, instance):
        if isinstance(instance, dict) and not isinstance(instance, _SafeDict):
            instance = _SafeDict(instance)
        data = super().to_representation(instance)
        if data.get("shortlist_count") is None:
            data["shortlist_count"] = 0
        return data
    



class CVSerializer(serializers.ModelSerializer):
    company = serializers.StringRelatedField()

    class Meta:
        model = CV
        fields = ["id", "name", "gender", "main_language", "second_language", "service_category_preference", "company"]


# ---------- WRITE / UPDATE OPERATIONS ----------

class ShortlistCreateSerializer(serializers.ModelSerializer):
    """Used when a CSR shortlists or removes a request."""
    class Meta:
        model = ShortlistedRequest
        fields = ["request"]


class CommitSerializer(serializers.Serializer):
    """Handles commit/uncommit from HTML forms."""
    request_id = serializers.CharField()
    

    def validate_request_id(self, value):
        from core.models import Request, RequestStatus
        try:
            req = Request.objects.get(pk=value)
        except Request.DoesNotExist:
            raise serializers.ValidationError("Request not found.")
        if req.status != RequestStatus.PENDING:
            raise serializers.ValidationError("Only PENDING requests can be committed.")
        return value


# ---------- MATCHING ----------

class CVSuggestionSerializer(serializers.Serializer):
    cv_id = serializers.CharField()
    score = serializers.FloatField()
    reason = serializers.DictField()


class MatchQueueSerializer(serializers.ModelSerializer):
    cv1queue = CVSerializer(read_only=True)
    cv2queue = CVSerializer(read_only=True)
    cv3queue = CVSerializer(read_only=True)

    class Meta:
        model = MatchQueue
        fields = [
            "request", "cv1queue", "cv2queue", "cv3queue",
            "current_index", "status", "sent_at", "deadline"
        ]


# ---------- NOTIFICATIONS ----------

class NotificationSerializer(serializers.ModelSerializer):
    cv = serializers.StringRelatedField()
    request = serializers.StringRelatedField()

    class Meta:
        model = Notification
        fields = ["id", "type", "message", "request", "cv", "meta", "created_at"]


# ---------- CLAIMS / COMPLETED ----------

class ClaimReportSerializer(serializers.ModelSerializer):
    cv = CVSerializer(read_only=True)
    request = serializers.StringRelatedField()

    class Meta:
        model = ClaimReport
        fields = [
            "id", "category", "amount", "payment_method",
            "description", "status", "created_at", "cv", "request"
        ]
