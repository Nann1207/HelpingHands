from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse

from .permissions import IsPlatformAdmin
from .admin_serializers import FlaggedRequestSerializer

from core.models import FlaggedRequest

from ..Control.admin_controllers import (
    AdminMetricsController, AdminFlagController, AdminReportController
)

class AdminMetricsView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    def get(self, request):
        data = AdminMetricsController.get_metrics(
            granularity=request.query_params.get("granularity", "day"),
            date_from=request.query_params.get("from"),
            date_to=request.query_params.get("to"),
        )
        return Response(data, status=200)

class AdminFlagsListView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    def get(self, request):
        resolved_q = request.query_params.get("resolved")
        resolved = None if resolved_q is None else (resolved_q.lower() == "true")
        qs = AdminFlagController.list_flags(
            resolved=resolved,
            flag_type=request.query_params.get("flag_type"),
            date_from=request.query_params.get("from"),
            date_to=request.query_params.get("to"),
        )
        return Response(FlaggedRequestSerializer(qs, many=True).data, status=200)

class AdminResolveFlagView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    def post(self, request, flag_id: int):
        notes = request.data.get("resolution_notes", "")
        try:
            flag = AdminFlagController.resolve_flag(flag_id=flag_id, pa_user=request.user, notes=notes)
        except FlaggedRequest.DoesNotExist:
            return Response({"detail":"Flag not found."}, status=404)
        except PermissionError as e:
            return Response({"detail":str(e)}, status=403)
        return Response(FlaggedRequestSerializer(flag).data, status=200)

class AdminReportView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    def get(self, request):
        filename, data = AdminReportController.export_requests_csv(
            date_from=request.query_params.get("from"),
            date_to=request.query_params.get("to"),
        )
        resp = HttpResponse(data, content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename=\"{filename}\"'
        return resp