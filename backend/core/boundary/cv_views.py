# core/Boundary/cv_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import PermissionDenied, ValidationError

from core.Control.cv_controller import CvController
from .cv_serializers import (
    CvRequestListSerializer,
    ClaimCreateSerializer, ClaimReportSerializer
)

# Create Class
class CvMyRequestsView(APIView):
    # GET /api/cv/requests/?status=active|complete
    def get(self, request):
        status_param = request.query_params.get("status")
        try:
            qs = CvController.list_requests(user=request.user, status=status_param)
        except (PermissionDenied, ValidationError) as e:
            return Response({"detail": str(e)}, status=400)
        return Response(CvRequestListSerializer(qs, many=True).data)

class CvCompleteRequestView(APIView):
    # POST /api/cv/requests/<req_id>/complete/
    def post(self, request, req_id):
        try:
            req = CvController.complete_request(user=request.user, req_id=req_id)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)
        return Response({"request_id": req.id, "status": req.status, "completed_at": req.completed_at}, status=200)

class CvSafetyTipsView(APIView):
    # GET /api/cv/requests/<req_id>/safety_tips/
    def get(self, request, req_id):
        try:
            data = CvController.safety_tips(user=request.user, req_id=req_id)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=403)
        return Response(data, status=200)

class CvCreateClaimView(APIView):
    # POST /api/cv/requests/<req_id>/claims/
    def post(self, request, req_id):
        ser = ClaimCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            claim = CvController.report_claim(user=request.user, req_id=req_id, **ser.validated_data)
        except (PermissionDenied, ValidationError) as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ClaimReportSerializer(claim).data, status=201)
