from rest_framework import serializers
from core.models import Request, ClaimReport, ChatRoom


class _ChatMixin(serializers.Serializer):
    chat_id = serializers.SerializerMethodField()
    chat_is_open = serializers.SerializerMethodField()

    def get_chat_id(self, obj):
        chat = getattr(obj, "chat", None)
        return chat.id if chat else None

    def get_chat_is_open(self, obj):
        chat = getattr(obj, "chat", None)
        return bool(chat and chat.is_open)

#  dashboard / lists 
class CvPendingItemSerializer(_ChatMixin, serializers.ModelSerializer):
    offered_rank = serializers.SerializerMethodField()
    offer_deadline = serializers.DateTimeField(source="match_queue.deadline", read_only=True)

    class Meta:
        model = Request
        fields = [
            "id", "service_type", "appointment_date", "appointment_time",
            "pickup_location", "service_location",
            "offered_rank", "offer_deadline",
            "chat_id", "chat_is_open",
        ]

    def get_offered_rank(self, obj):
        mq = getattr(obj, "match_queue", None)
        return mq.current_index if mq else None

class CvRequestListSerializer(_ChatMixin, serializers.ModelSerializer):
    class Meta:
        model = Request
        fields = [
            "id", "status", "service_type", "appointment_date", "appointment_time",
            "pickup_location", "service_location", "created_at", "completed_at",
            "chat_id", "chat_is_open",
        ]

class CvRequestDetailSerializer(_ChatMixin, serializers.ModelSerializer):
    pin_name = serializers.CharField(source="pin.name", read_only=True)
    pin_gender_pref = serializers.CharField(source="pin.preferred_cv_gender", read_only=True)
    pin_lang_pref = serializers.CharField(source="pin.preferred_cv_language", read_only=True)

    class Meta:
        model = Request
        fields = [
            "id", "status", "service_type",
            "appointment_date", "appointment_time",
            "pickup_location", "service_location",
            "description",
            "pin_name", "pin_gender_pref", "pin_lang_pref",
            "chat_id", "chat_is_open",
            "created_at", "completed_at",
        ]

#  claims 
class ClaimCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimReport
        fields = ["category", "expense_date", "amount", "payment_method", "description", "receipt"]

class ClaimReportSerializer(serializers.ModelSerializer):
    receipt_url = serializers.SerializerMethodField()
    request_id = serializers.CharField(source="request.id", read_only=True)

    class Meta:
        model = ClaimReport
        fields = [
            "id", "request_id", "cv",
            "category", "expense_date", "amount",
            "payment_method", "description",
            "status", "created_at", "updated_at",
            "receipt_url",
        ]
        read_only_fields = ["cv", "status", "created_at", "updated_at", "request_id"]

    def get_receipt_url(self, obj):
        try:
            if obj.receipt:
                request = self.context.get("request")
                url = obj.receipt.url
                return request.build_absolute_uri(url) if request else url
        except Exception:
            pass
        return None
