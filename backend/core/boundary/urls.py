# core/boundary/urls.py

from django.urls import path
from .admin_views import (
    AdminMetricsView,
    AdminFlagsListView,
    AdminAcceptFlagView,
    AdminRejectFlagView,
    AdminReportView,
)
from .auth_views import auth_login, auth_me, auth_logout

urlpatterns = [

    # AUTHENTICATION ENDPOINTS

    # POST /api/auth/login/
    path("auth/login/", auth_login, name="auth-login"),

    # GET /api/auth/me/
    path("auth/me/", auth_me, name="auth-me"),

    # POST /api/auth/logout/
    path("auth/logout/", auth_logout, name="auth-logout"),


    # PLATFORM ADMIN ENDPOINTS

    # GET /api/admin/metrics/
    path("admin/metrics/", AdminMetricsView.as_view(), name="admin-metrics"),

    # GET /api/admin/flags/
    path("admin/flags/", AdminFlagsListView.as_view(), name="admin-flags-list"),

    # POST /api/admin/flags/<flag_id>/accept/
    path("admin/flags/<int:flag_id>/accept/", AdminAcceptFlagView.as_view(), name="admin-flag-accept"),

    # POST /api/admin/flags/<flag_id>/reject/
    path("admin/flags/<int:flag_id>/reject/", AdminRejectFlagView.as_view(), name="admin-flag-reject"),

    # GET /api/admin/reports/requests.csv
    path("admin/reports/requests.csv", AdminReportView.as_view(), name="admin-report-requests"),
]
