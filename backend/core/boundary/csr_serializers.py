# core/boundary/csr_serializers.py
from rest_framework import serializers
from core.models import Request, CV

class CSRRequestListSerializer(serializers.ModelSerializer):
    shortlist_count = serializers.IntegerField(source="shortlisted_by.count", read_only=True)

    class Meta:
        model = Request
        fields = [
            "id", "service_type", "status",
            "appointment_date", "appointment_time",
            "pickup_location", "service_location",
            "description", "created_at", "shortlist_count",
        ]
# class for brief CV serializer
class CVBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = CV
        fields = ["id", "name", "gender", "main_language", "second_language", "service_category_preference"]
# class for CV suggestion serializer
class CVSuggestionSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    gender = serializers.CharField()
    main_language = serializers.CharField()
    second_language = serializers.CharField(allow_null=True, allow_blank=True)
    service_category_preference = serializers.CharField()
    svc_match = serializers.IntegerField()
    completed_count = serializers.IntegerField()
    active_load = serializers.IntegerField()
