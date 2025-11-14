# core/entity/chat_entity.py
from __future__ import annotations
from typing import Optional
from django.db import transaction
from core.models import ChatRoom, Request, RequestStatus
import django.utils.timezone as timezone
from datetime import timedelta  

class ChatEntity:



    #Ensures that there is only one chat per request, no duplicates
    @staticmethod
    @transaction.atomic
    def get_or_create_for_request(req: Request) -> ChatRoom:
        #Looks for an existing chat that belongs to the given request, if not create
        chat, _ = ChatRoom.objects.get_or_create(request=req)
        return chat




    #fetch all chats belong to CV
    @staticmethod
    def list_for_cv(cv_id: str, *, status: Optional[str] = None):

        qs = ChatRoom.objects.filter(request__cv_id=cv_id) #Used to finds chats where the linked request cv_id matches the current CV
        if status == "open": #queryset method to get only chats that are currently open
            qs = qs.open()
        elif status == "closed": #Gets all expired or not-yet-open chats.
            qs = qs.closed()
        return qs.select_related("request").order_by("-opens_at") #preloads related Request data in one SQL query and orders chats by most recent first



    #fetch all chats belong to PIN
    @staticmethod
    def list_for_pin(pin_id: str, *, status: Optional[str] = None):
        qs = ChatRoom.objects.filter(request__pin_id=pin_id) ##Used to finds chats where the linked request pin_id matches the current PIN
        if status == "open":
            qs = qs.open()
        elif status == "closed":
            qs = qs.closed()
        return qs.select_related("request").order_by("-opens_at")
    

    @staticmethod
    @transaction.atomic
    def complete_request(req: Request) -> Request:
        if req.status != RequestStatus.COMPLETE:
            req.status = RequestStatus.COMPLETE
            if not req.completed_at:
                req.completed_at = timezone.now()
        else:
            req.completed_at = req.completed_at or timezone.now()
        req.save(update_fields=["status", "completed_at"])

        chat, _ = ChatRoom.objects.get_or_create(request=req)
        desired_expiry = req.completed_at + timedelta(hours=24)
        if chat.expires_at != desired_expiry:
            chat.expires_at = desired_expiry
            chat.save(update_fields=["expires_at"])
        return req
