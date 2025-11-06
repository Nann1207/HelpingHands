
from django.urls import path
from .admin_views import (
    AdminMetricsView,
    AdminFlagsListView,
    AdminResolveFlagView,
    AdminReportView,
)
from . import auth_views

urlpatterns = [
    path("auth/login/", auth_views.auth_login, name="auth_login"),
    path("auth/me/", auth_views.auth_me, name="auth_me"),
    path("auth/logout/", auth_views.auth_logout, name="auth_logout"),
    path("admin/metrics/", AdminMetricsView.as_view(), name="admin-metrics"),
    path("admin/flags/", AdminFlagsListView.as_view(), name="admin-flags"),
    path("admin/flags/<int:flag_id>/resolve/", AdminResolveFlagView.as_view(), name="admin-flag-resolve"),
    path("admin/report/", AdminReportView.as_view(), name="admin-report"),
]
