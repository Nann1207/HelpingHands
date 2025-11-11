# core/boundary/chat_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404

from core.Control.chat_controller import ChatController
from core.models import ChatRoom
from .chat_serializers import (
    ChatRoomSerializer,
    ChatMessageSerializer,
    ChatMessageCreateSerializer,
)




#GET /api/me/chats/?status=all|open|closed
#list chats for the current logged-in user.
class MyChatsView(APIView):
    def get(self, request):
        status_param = request.query_params.get("status")
        status_param = None if status_param in (None, "all") else status_param
        chats = ChatController.list_my_chats(user=request.user, status=status_param) #Fetch chats based on cv or pin
        return Response(ChatRoomSerializer(chats, many=True).data) #serilaisers to convert chat objects to JSON




#POST /api/requests/<req_id>/chat/
class RequestChatView(APIView):
    def post(self, request, req_id):
        try:
            chat = ChatController.get_or_create_for_request(user=request.user, req_id=req_id)
        except PermissionDenied:
            return Response({"detail": "Not allowed."}, status=403)
        return Response(ChatRoomSerializer(chat).data, status=status.HTTP_201_CREATED)



class ChatMessagesListCreate(APIView):
    """
    GET  /api/chats/<chat_id>/messages/
    POST /api/chats/<chat_id>/messages/
    """

    def get(self, request, chat_id):
        chat = get_object_or_404(ChatRoom, pk=chat_id)
        try:
            ChatController._ensure_cv_or_pin(request.user, chat.request)
        except PermissionDenied:
            return Response({"detail": "Not allowed."}, status=403)

        msgs = chat.messages.order_by("created_at")
        return Response(ChatMessageSerializer(msgs, many=True).data)

    def post(self, request, chat_id):
        # Use serializer for input validation
        ser = ChatMessageCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        body = ser.validated_data["body"]

        try:
            msg = ChatController.send_message(
                user=request.user,
                chat_id=chat_id,
                body=body
            )
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)
        except ValidationError as e:
            return Response({"detail": str(e)}, status=400)

        return Response(ChatMessageSerializer(msg).data, status=201)
    





# 4) Mark request COMPLETE (and expire chat 24h after completion)
class CompleteRequestView(APIView):
    """
    POST /api/requests/<req_id>/complete/
      -> sets Request.status=COMPLETE (+ completed_at if missing)
      -> sets chat.expires_at = completed_at + 24h
    """
    def post(self, request, req_id):
        try:
            req = ChatController.complete_request(user=request.user, req_id=req_id)
        except PermissionDenied:
            return Response({"detail": "Not allowed."}, status=403)
        return Response({"request_id": req.id, "status": req.status, "completed_at": req.completed_at}, status=200)