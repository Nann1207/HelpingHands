# core/boundary/admin_views.py
from rest_framework.views import APIView #APIView comes from Django REST Framework, class that knows how to handle HTTP requests 
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



# GET /api/admin/metrics/
class AdminMetricsView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]  #The user must be logged in and a PA, else will return a 403 error

    def get(self, request): #GET request, request is basically extra info sent along with an API request (like authentication tokens, content type, or browser info) and user info
        data = AdminMetricsController.get_metrics(
            granularity=request.query_params.get("granularity", "day"), #query_params is to read data sent in the URL query, if no date its just default
            date_from=request.query_params.get("from"),
            date_to=request.query_params.get("to"),
        )
        return Response(data, status=status.HTTP_200_OK) #converts your Python dict data into JSON.  HTTP status code 200 means sucess


# This is for Admin Flags view
class AdminFlagsListView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin] #The user must be logged in and a PA

    def get(self, request):
        resolved_q = request.query_params.get("resolved")
        resolved = None if resolved_q is None else (resolved_q.lower() == "true")

        qs = AdminFlagController.list_flags(
            resolved=resolved,
            flag_type=request.query_params.get("flag_type"),
            date_from=request.query_params.get("from"),
            date_to=request.query_params.get("to"),
        )
        return Response(FlaggedRequestSerializer(qs, many=True).data, status=status.HTTP_200_OK) #serializes the queryset into JSON and returns 200



#POST /api/admin/flags/{flag_id}/accept/
class AdminAcceptFlagView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin] #The user must be logged in and a PA

    def post(self, request, flag_id: int):
        notes = request.data.get("resolution_notes", "")  
        try:
            flag = AdminFlagController.accept_flag(flag_id=flag_id, pa_user=request.user, notes=notes)
        except FlaggedRequest.DoesNotExist:
            return Response({"detail": "Flag not found."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN) #Returns 404 if flag ID doesn’t exist and 403 if the user isn’t PA

        return Response(FlaggedRequestSerializer(flag).data, status=status.HTTP_200_OK) #Returns the serialized flag data with 200 OK


#POST /api/admin/flags/{flag_id}/reject/
class AdminRejectFlagView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def post(self, request, flag_id: int):
        notes = (request.data.get("resolution_notes") or "").strip()
        if not notes:
            return Response({"detail": "resolution_notes is required to reject."},
                            status=status.HTTP_400_BAD_REQUEST) #If no notes provided, return 400 Bad Request
        try:
            flag = AdminFlagController.reject_flag(flag_id=flag_id, pa_user=request.user, notes=notes)
        except FlaggedRequest.DoesNotExist:
            return Response({"detail": "Flag not found."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN) # #Returns 404 if flag ID doesn’t exist and 403 if the user isn’t PA

        return Response(FlaggedRequestSerializer(flag).data, status=status.HTTP_200_OK) ##Returns the serialized flag data with 200 OK


#GET /api/admin/reports/requests.csv
class AdminReportView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        filename, data = AdminReportController.export_requests_csv(
            date_from=request.query_params.get("from"),
            date_to=request.query_params.get("to"),
        )
        resp = HttpResponse(data, content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp
