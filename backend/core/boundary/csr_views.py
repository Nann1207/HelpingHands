# core/boundary/csr_views.py
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.Control.csr_controller import CSRController
from core.models import Request, CV, Notification

# ---- Inline serializers (keeps the file self-contained) ----

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


class NotificationSerializer(serializers.ModelSerializer):
    request_id = serializers.CharField(source="request.id", allow_null=True, read_only=True)
    cv_id = serializers.CharField(source="cv.id", allow_null=True, read_only=True)
    cv_name = serializers.CharField(source="cv.name", allow_null=True, read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "type", "message", "request_id", "cv_id", "cv_name", "meta", "created_at", "is_read"]


# ---- Views ----

class CSRPendingRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = CSRController.list_pending(request.user)
        return Response(CSRRequestListSerializer(qs, many=True).data)


class CSRShortlistsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = CSRController.list_shortlisted(request.user)
        return Response(CSRRequestListSerializer(qs, many=True).data)

    def post(self, request):
        req_id = request.data.get("request_id")
        if not req_id:
            return Response({"detail": "request_id is required."}, status=400)
        CSRController.shortlist(request.user, req_id)
        return Response({"ok": True})

    def delete(self, request):
        req_id = request.data.get("request_id")
        if not req_id:
            return Response({"detail": "request_id is required."}, status=400)
        CSRController.unshortlist(request.user, req_id)
        return Response(status=204)


class CSRFlagRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, req_id: str):
        reason = request.data.get("reason", "")
        flag = CSRController.flag_request(request.user, req_id, reason)
        return Response({"flag_id": getattr(flag, "id", None), "status": "created"}, status=201)


# ---- Suggestions + Queue endpoints ----

class CSRMatchSuggestionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, req_id: str):
        data = CSRController.get_suggestions(request.user, req_id)
        return Response(CVSuggestionSerializer(data, many=True).data, status=200)


class CSRCreateQueueView(APIView):
    """
    POST body: { "cv_ids": ["CVxxxx","CVyyyy","CVzzzz"] } (ordered, length 1..3)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, req_id: str):
        ids = request.data.get("cv_ids") or []
        mq = CSRController.create_queue(request.user, req_id, ids)
        payload = {
            "request_id": mq.request_id,
            "cv1": getattr(mq.cv1, "id", None),
            "cv2": getattr(mq.cv2, "id", None),
            "cv3": getattr(mq.cv3, "id", None),
            "current_index": mq.current_index,
            "status": mq.status,
        }
        return Response(payload, status=201)


class CSRStartQueueView(APIView):
    """
    POST body (optional): { "hours_to_respond": 1 }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, req_id: str):
        hours = int(request.data.get("hours_to_respond", 1))
        current_cv = CSRController.start_queue(request.user, req_id, hours_to_respond=hours)
        return Response({"current_cv": getattr(current_cv, "id", None)}, status=200)


class CSRAdvanceQueueView(APIView):
    """
    Manually advance after a decline/timeout sweep; returns the new current CV (if any).
    POST body (optional): { "hours_to_respond": 1 }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, req_id: str):
        hours = int(request.data.get("hours_to_respond", 1))
        next_cv = CSRController.advance_queue(request.user, req_id, hours_to_respond=hours)
        return Response({"current_cv": getattr(next_cv, "id", None)}, status=200)


# ---- Notifications ----

class MyNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread_only = request.query_params.get("unread") in ("1", "true", "yes")
        qs = Notification.objects.filter(recipient=request.user)
        if unread_only:
            qs = qs.filter(is_read=False)
        qs = qs.order_by("-created_at")[:100]
        return Response(NotificationSerializer(qs, many=True).data)


class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notif_id: int):
        n = get_object_or_404(Notification, pk=notif_id, recipient=request.user)
        if not n.is_read:
            n.is_read = True
            n.save(update_fields=["is_read"])
        return Response({"ok": True})


class MarkAllNotificationsReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({"ok": True})
