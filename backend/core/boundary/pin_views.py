# core/Boundary/pin_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import PermissionDenied, ValidationError

from core.Control.pin_controller import PinController
from core.models import Request, ClaimReport
from .pin_serializers import (
    RequestCreateSerializer, RequestListSerializer,
    ProfileUpdateSerializer, OtpCodeSerializer,
    ClaimReportSerializer, DisputeSerializer
)

class PinRequestCreateView(APIView):
    # POST /api/pin/requests/
    def post(self, request):
        ser = RequestCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        req = PinController.submit_request(user=request.user, **ser.validated_data)
        return Response(RequestListSerializer(req).data, status=201)

class PinMyRequestsView(APIView):
    # GET /api/pin/requests/?status=review|pending|active|complete
    def get(self, request):
        status_param = request.query_params.get("status")
        qs = PinController.list_my_requests(user=request.user, status=status_param)
        return Response(RequestListSerializer(qs, many=True).data)

class PinStartProfileUpdateView(APIView):
    # POST /api/pin/profile/otp/start
    def post(self, request):
        out = PinController.start_profile_update_otp(user=request.user)
        return Response(out, status=200)

class PinConfirmProfileUpdateView(APIView):
    # POST /api/pin/profile/otp/confirm
    def post(self, request):
        ser = ProfileUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            pin = PinController.confirm_profile_update(
                user=request.user, code=ser.validated_data["code"],
                **ser.validated_data["fields"]
            )
        except ValidationError as e:
            return Response({"detail": str(e)}, status=400)
        return Response({"ok": True})

class PinClaimsView(APIView):
    # GET /api/pin/claims/ (completed requests w/ claims)
    def get(self, request):
        data = PinController.list_completed_with_claims(user=request.user)
        return Response(ClaimReportSerializer(data, many=True).data)

class PinVerifyClaimView(APIView):
    # POST /api/pin/claims/<claim_id>/verify
    def post(self, request, claim_id):
        try:
            claim = PinController.verify_claim(user=request.user, claim_id=claim_id)
            return Response({"ok": True, "status": claim.status}, status=200)
        except (PermissionDenied, ValidationError) as e:
            return Response({"detail": str(e)}, status=403)

class PinDisputeClaimView(APIView):
    # POST /api/pin/claims/<claim_id>/dispute
    def post(self, request, claim_id):
        ser = DisputeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            dispute = PinController.dispute_claim(
                user=request.user, claim_id=claim_id,
                reason=ser.validated_data["reason"],
                comment=ser.validated_data.get("comment", "")
            )
            return Response({"ok": True}, status=201)
        except (PermissionDenied, ValidationError) as e:
            return Response({"detail": str(e)}, status=400)
