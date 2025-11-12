from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import PermissionDenied, ValidationError

from core.Control.cv_controller import CvController
from .cv_serializers import (
    CvPendingItemSerializer,
    CvRequestListSerializer,
    CvRequestDetailSerializer,
    ClaimCreateSerializer, ClaimReportSerializer
)

# ---------- Dashboard: three sections ----------

class CvDashboardView(APIView):
    # GET /api/cv/dashboard/
    def get(self, request):
        try:
            data = CvController.dashboard(user=request.user)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)

        payload = {
            "pending": CvPendingItemSerializer(data["pending"], many=True).data,
            "active": CvRequestListSerializer(data["active"], many=True).data,
            "completed": CvRequestListSerializer(data["completed"], many=True).data,
        }
        return Response(payload, status=200)

# ---------- Pending: decision endpoints ----------

class CvOfferDecisionView(APIView):
    # POST /api/cv/requests/<req_id>/decision/   { "accepted": true|false }
    def post(self, request, req_id):
        accepted = bool(request.data.get("accepted"))
        try:
            result = CvController.decide_offer(user=request.user, req_id=req_id, accepted=accepted)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)
        except ValidationError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(result, status=200)

# ---------- Lists ----------

class CvMyRequestsView(APIView):
    # GET /api/cv/requests/?status=active|complete
    def get(self, request):
        status_param = request.query_params.get("status")
        try:
            qs = CvController.list_requests(user=request.user, status=status_param)
        except (PermissionDenied, ValidationError) as e:
            return Response({"detail": str(e)}, status=400)
        return Response(CvRequestListSerializer(qs, many=True).data, status=200)

# ---------- Detail ----------

class CvRequestDetailView(APIView):
    # GET /api/cv/requests/<req_id>/
    def get(self, request, req_id):
        try:
            req_obj = CvController.request_detail(user=request.user, req_id=req_id)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)
        return Response(CvRequestDetailSerializer(req_obj).data, status=200)

# ---------- Safety Tips ----------

class CvSafetyTipsView(APIView):
    # GET /api/cv/requests/<req_id>/safety_tips/
    def get(self, request, req_id):
        try:
            data = CvController.safety_tips(user=request.user, req_id=req_id)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)
        return Response(data, status=200)

# ---------- Complete ----------

class CvCompleteRequestView(APIView):
    # POST /api/cv/requests/<req_id>/complete/
    def post(self, request, req_id):
        try:
            req = CvController.complete_request(user=request.user, req_id=req_id)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)
        return Response({"request_id": req.id, "status": req.status, "completed_at": req.completed_at}, status=200)

# ---------- Claims ----------

class CvCreateClaimView(APIView):
    # POST /api/cv/requests/<req_id>/claims/
    def post(self, request, req_id):
        ser = ClaimCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            claim = CvController.report_claim(user=request.user, req_id=req_id, **ser.validated_data)
        except (PermissionDenied, ValidationError) as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ClaimReportSerializer(claim, context={"request": request}).data, status=201)

class CvMyClaimsView(APIView):
    # GET /api/cv/claims/
    def get(self, request):
        try:
            qs = CvController.list_claims(user=request.user)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)
        return Response(ClaimReportSerializer(qs, many=True, context={"request": request}).data, status=200)
