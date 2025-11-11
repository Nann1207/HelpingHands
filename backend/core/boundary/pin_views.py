# core/boundary/pin_views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import PermissionDenied, ValidationError

from core.Control.pin_controller import PinController
from core.models import Request, ClaimReport
from .pin_serializers import (
    RequestCreateSerializer, RequestListSerializer,
    ProfileUpdateSerializer, PasswordChangeSerializer,
    PinClaimSerializer, DisputeSerializer
)
from .cv_serializers import ClaimReportSerializer



#When a PIN user wants to create a new service request.
class PinRequestCreateView(APIView):
    # POST /api/pin/requests/
    def post(self, request):
        ser = RequestCreateSerializer(data=request.data) #Uses RequestCreateSerializer to check that the input data is valid.
        ser.is_valid(raise_exception=True)
        req = PinController.submit_request(user=request.user, **ser.validated_data) #controller’s submit_request() to create the Request, moderation and submit
        return Response(RequestListSerializer(req).data, status=201)


#To list all service requests made by PIN user, filtered by status.
class PinMyRequestsView(APIView):
    # GET /api/pin/requests/?status=review|pending|active|complete.
    def get(self, request):
        status_param = request.query_params.get("status")
        qs = PinController.list_my_requests(user=request.user, status=status_param)
        return Response(RequestListSerializer(qs, many=True).data)


#To start the OTP process for updating profile information.
class PinStartProfileUpdateView(APIView):
    # POST /api/pin/profile/otp/start
    def post(self, request):
        out = PinController.start_profile_update_otp(user=request.user)
        return Response(out, status=200)


#To confirm the OTP and update profile information.
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


#Displays all claims related to the pin completed requests.
    # GET /api/pin/claims/ 
class PinClaimsView(APIView):
    def get(self, request):
        qs = ClaimReport.objects.filter(request__pin__user=request.user)
        ser = PinClaimSerializer(qs, many=True, context={"request": request})
        return Response(ser.data)

#Agrees that a claim is correct and verifies it.
class PinVerifyClaimView(APIView):
    # POST /api/pin/claims/<claim_id>/verify
    def post(self, request, claim_id):
        try:
            claim = PinController.verify_claim(user=request.user, claim_id=claim_id)
            return Response({"ok": True, "status": claim.status}, status=200)
        except (PermissionDenied, ValidationError) as e:
            return Response({"detail": str(e)}, status=403)

#Disputes a claim made by the CV user.
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


class PinStartPasswordOTPView(APIView):
    # POST /api/pin/password/otp/start/
    def post(self, request):
        # reuse the same email sending logic but for PASSWORD_CHANGE
        # simplest: call a tiny helper on controller that issues an OTP for PASSWORD_CHANGE
        # If you don't have it yet, see controller snippet below.
        out = PinController.start_password_change_otp(user=request.user)
        return Response(out, status=200)


class PinChangePasswordView(APIView):
    # POST /api/pin/password/change/
    def post(self, request):
        ser = PasswordChangeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            PinController.change_password_with_otp(
                user=request.user,
                code=ser.validated_data["code"],
                new_password=ser.validated_data["new_password"],
            )
            return Response({"ok": True}, status=200)
        except ValidationError as e:
            return Response({"detail": str(e)}, status=400)
