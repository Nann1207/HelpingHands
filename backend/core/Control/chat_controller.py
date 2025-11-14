# core/Control/chat_controller.py
from __future__ import annotations
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import get_object_or_404 
from django.core.exceptions import PermissionDenied, ValidationError
from core.models import Request, ChatRoom
from core.entity.chat_entity import ChatEntity

class ChatController:

    #Ensure CV or PIN is associated with the request
    @staticmethod
    def _ensure_cv_or_pin(user, req: Request):
        ok = False
        if hasattr(user, "cv") and req.cv_id and user.cv.id == req.cv_id:
            ok = True
        if hasattr(user, "personinneed") and user.personinneed.id == req.pin_id:
            ok = True
        if not ok:
            raise PermissionDenied("Not allowed.") #raises if not


    #Fetch the request by ID, 
    @staticmethod
    def get_or_create_for_request(*, user, req_id: str) -> ChatRoom:
        req = get_object_or_404(Request, pk=req_id)
        ChatController._ensure_cv_or_pin(user, req) #Make sure the user is allowed to access it
        return ChatEntity.get_or_create_for_request(req) #create the chat
    
    #Fetch a chat 
    @staticmethod
    def get_chat(*, user, chat_id: str) -> ChatRoom:
        chat = ChatEntity.get_chat(chat_id)
        ChatController._ensure_cv_or_pin(user, chat.request)
        return chat


    #Detects if the current user is a CV or PIN and lists their chats accordingly
    @staticmethod
    def list_my_chats(*, user, status: str | None):
        if hasattr(user, "cv"):
            return ChatEntity.list_for_cv(user.cv.id, status=status)
        if hasattr(user, "personinneed"):
            return ChatEntity.list_for_pin(user.personinneed.id, status=status)
        return ChatRoom.objects.none()


    #Send a message in a chat
    @staticmethod
    def send_message(*, user, chat_id: str, body: str):
        chat = ChatController.get_chat(user=user, chat_id=chat_id) 

        if not chat.is_open:
            raise PermissionDenied("Chat is closed.")

        body = (body or "").strip()
        if not body:
            raise ValidationError("Message body cannot be empty.")

        return ChatEntity.save_message(chat, sender=user, body=body)




    #Close out a request and set chat expiry
    @staticmethod
    def complete_request(*, user, req_id: str):
        req = get_object_or_404(Request, pk=req_id)
        ChatController._ensure_cv_or_pin(user, req)
        return ChatEntity.complete_request(req)

