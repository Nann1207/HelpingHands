# core/Boundary/csr_views.py


from __future__ import annotations
from typing import List

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, serializers

from core.models import CSRRep, RequestStatus

from core.Control.csr_controller import (
    CSRDashboardController, CSRRequestController, CSRShortlistController,
    CSRCommitController, CSRMatchController, CSRNotificationController,
    CSRCompletedController,
)
from core.boundary.csr_serializers import (
    RequestListSerializer,
    NotificationSerializer,
    ClaimReportSerializer,
    CVSuggestionSerializer,
    ShortlistCreateSerializer,
    CommitSerializer,
)


# ---- Permissions -------------------------------------------------------------

class IsCSRRep:
    def has_permission(self, request, view):
        return hasattr(request.user, "csrrep")


def _csr(request) -> CSRRep:
    return request.user.csrrep


# ---- Response serializers (UI-shaped) ---------------------------------------

class ComingSoonResponseSerializer(serializers.Serializer):
    coming_soon = RequestListSerializer(many=True)
    all_requests = RequestListSerializer(many=True)


class DashboardResponseSerializer(serializers.Serializer):
    today_active = RequestListSerializer(many=True)
    committed = RequestListSerializer(many=True)
    notifications = NotificationSerializer(many=True)


class _SafeShortlistRow(dict):
    """Gracefully return None for missing keys when serializing shortlist rows."""

    def __missing__(self, key):
        return None


class ShortlistItemSerializer(serializers.Serializer):
    shortlist_id = serializers.IntegerField()
    request_id = serializers.CharField()
    pin = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    category = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    service_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    appointment_date = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    location = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    service_location = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def to_representation(self, instance):
        if isinstance(instance, dict) and not isinstance(instance, _SafeShortlistRow):
            instance = _SafeShortlistRow(instance)
        data = super().to_representation(instance)
        if not data.get("category"):
            data["category"] = data.get("service_type") or ""
        if not data.get("location"):
            data["location"] = data.get("service_location") or ""
        return data


class CommitResponseSerializer(serializers.Serializer):
    id = serializers.CharField()
    status = serializers.ChoiceField(choices=RequestStatus.choices)


class CVDecisionSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()


class ClaimDecisionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["reimburse", "reject"])


# ---- 1) Dashboard ------------------------------------------------------------

class CSRDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsCSRRep]

    def get(self, request):
        data = CSRDashboardController.get_dashboard(_csr(request))
        return Response(DashboardResponseSerializer(data).data, status=status.HTTP_200_OK)


# ---- 2) Requests Pool --------------------------------------------------------

class CSRRequestPoolView(APIView):
    permission_classes = [IsAuthenticated, IsCSRRep]

    def get(self, request):
        data = CSRRequestController.list_pool()
        return Response(ComingSoonResponseSerializer(data).data, status=status.HTTP_200_OK)


class CSRShortlistToggleView(APIView):
    permission_classes = [IsAuthenticated, IsCSRRep]

    def post(self, request, request_id: str):
        csr = _csr(request)
        ser = ShortlistCreateSerializer(data={"request": request_id}, context={"csr": csr})
        ser.is_valid(raise_exception=True)
        data = CSRRequestController.shortlist_add(csr, request_id)
        # shape to ShortlistItemSerializer-like row for your HTML table
        row = {
            "shortlist_id": data["id"],
            "request_id": data["request_id"],
            "pin": data.get("pin", ""),
            "service_type": data.get("service_type", ""),
            "appointment_date": data.get("appointment_date", ""),
            "service_location": data.get("service_location", ""),
        }
        return Response(ShortlistItemSerializer(row).data, status=status.HTTP_201_CREATED)

    def delete(self, request, request_id: str):
        data = CSRRequestController.shortlist_remove(_csr(request), request_id)
        return Response(data, status=status.HTTP_200_OK)


class CSRCommitFromPoolView(APIView):
    permission_classes = [IsAuthenticated, IsCSRRep]

    def post(self, request, request_id: str):
        ser = CommitSerializer(data={"request_id": request_id})
        ser.is_valid(raise_exception=True)
        data = CSRRequestController.commit_request(_csr(request), request_id)
        return Response(CommitResponseSerializer(data).data, status=status.HTTP_200_OK)


# ---- 3) Shortlist Page -------------------------------------------------------

class CSRShortlistView(APIView):
    permission_classes = [IsAuthenticated, IsCSRRep]

    def get(self, request):
        data = CSRShortlistController.list(_csr(request))
        items = ShortlistItemSerializer(data["items"], many=True).data
        return Response({"items": items}, status=status.HTTP_200_OK)


# ---- 4) Commit Page ----------------------------------------------------------

class CSRCommitListView(APIView):
    permission_classes = [IsAuthenticated, IsCSRRep]

    def get(self, request):
        data = CSRCommitController.list(_csr(request))
        # Controller returns {"items": [...]} where each is request-like
        items = RequestListSerializer(data["items"], many=True).data
        return Response({"items": items}, status=status.HTTP_200_OK)


# ---- 5) Match Details --------------------------------------------------------

class CSRMatchSuggestView(APIView):
    permission_classes = [IsAuthenticated, IsCSRRep]

    def get(self, request, request_id: str):
        data = CSRMatchController.suggest(request_id)  # {"suggestions": [{cv_id, score, reason}, ...]}
        suggestions = CVSuggestionSerializer(data["suggestions"], many=True).data
        return Response({"suggestions": suggestions}, status=status.HTTP_200_OK)


class CSRMatchAssignmentPoolView(APIView):
    permission_classes = [IsAuthenticated, IsCSRRep]

    class _Payload(serializers.Serializer):
        cv_ids = serializers.ListField(child=serializers.CharField(), min_length=1, max_length=3)

    def get(self, request, request_id: str):
        data = CSRMatchController.get_assignment_pool(request_id)
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, request_id: str):
        payload = self._Payload(data=request.data)
        payload.is_valid(raise_exception=True)
        data = CSRMatchController.set_assignment_pool(request_id, payload.validated_data["cv_ids"])
        return Response(data, status=status.HTTP_200_OK)  # already shaped; optionally use MatchQueueSerializer


class CSRSendOffersView(APIView):
    permission_classes = [IsAuthenticated, IsCSRRep]

    class _Payload(serializers.Serializer):
        timeout_minutes = serializers.IntegerField(min_value=1, default=30, required=False)

    def post(self, request, request_id: str):
        payload = self._Payload(data=request.data)
        payload.is_valid(raise_exception=True)
        timeout = payload.validated_data.get("timeout_minutes", 30)
        data = CSRMatchController.send_offers(request_id, timeout)
        return Response(data, status=status.HTTP_200_OK)  # optionally MatchQueueSerializer


class CVCandidateDecisionView(APIView):
    permission_classes = [IsAuthenticated]  # adjust if CV auth differs

    def post(self, request, request_id: str, cv_id: str):
        ser = CVDecisionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = CSRMatchController.cv_decision(request_id, cv_id, ser.validated_data["accepted"])
        return Response(data, status=status.HTTP_200_OK)


class DormantSweepView(APIView):
    permission_classes = [IsAuthenticated, IsCSRRep]

    def post(self, request):
        data = CSRMatchController.sweep_dormant()
        return Response(data, status=status.HTTP_200_OK)


# ---- 6) Notifications --------------------------------------------------------

class CSRNotificationsView(APIView):
    permission_classes = [IsAuthenticated, IsCSRRep]

    def get(self, request):
        data = CSRNotificationController.list(request.user)  # {"items":[...]}
        return Response(NotificationSerializer(data["items"], many=True).data, status=status.HTTP_200_OK)


# ---- 7) Completed Requests & Claims -----------------------------------------

class CSRCompletedView(APIView):
    permission_classes = [IsAuthenticated, IsCSRRep]

    def get(self, request):
        data = CSRCompletedController.list(_csr(request))  # {"items":[...]}
        return Response(RequestListSerializer(data["items"], many=True).data, status=status.HTTP_200_OK)


class CSRCompletedClaimsView(APIView):
    permission_classes = [IsAuthenticated, IsCSRRep]

    def get(self, request, request_id: str):
        claims = CSRCompletedController.claims(request_id)

        serializer = ClaimReportSerializer(claims, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)







class CSRClaimDecisionView(APIView):
    permission_classes = [IsAuthenticated, IsCSRRep]

    def post(self, request, claim_id: str):
        ser = ClaimDecisionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        action = ser.validated_data["action"]
        if action == "reimburse":
            data = CSRCompletedController.reimburse(claim_id)
        else:
            data = CSRCompletedController.reject(claim_id)
        return Response(data, status=status.HTTP_200_OK)
