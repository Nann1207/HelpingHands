# core/boundary/chat_serializers.py
from rest_framework import serializers
from core.models import ChatRoom, ChatMessage

class ChatRoomSerializer(serializers.ModelSerializer):
    is_open = serializers.SerializerMethodField()
    request_id = serializers.CharField(source="request.id", read_only=True)
    service_type = serializers.CharField(source="request.service_type", read_only=True)

    class Meta:
        model = ChatRoom
        fields = ["id", "request_id", "service_type", "opens_at", "expires_at", "is_open", "created_at"]

    def get_is_open(self, obj):
        return obj.is_open

class ChatMessageSerializer(serializers.ModelSerializer):
    sender = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = ChatMessage
        fields = ["id", "room", "sender", "body", "created_at"]
        read_only_fields = ["id", "room", "sender", "created_at"]

class ChatMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000)
