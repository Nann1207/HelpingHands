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

# PIN
from .pin_views import (
    PinRequestCreateView, PinMyRequestsView,
    PinStartProfileUpdateView, PinConfirmProfileUpdateView,
    PinClaimsView, PinVerifyClaimView, PinDisputeClaimView
)

# CV
from .cv_views import (
    CvMyRequestsView, CvCompleteRequestView, CvSafetyTipsView, CvCreateClaimView
)

from .chat_views import MyChatsView, RequestChatView, ChatMessagesListCreate, CompleteRequestView

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

    # PIN
    path("pin/requests/", PinRequestCreateView.as_view()),
    path("pin/requests/list/", PinMyRequestsView.as_view()),
    path("pin/profile/otp/start/", PinStartProfileUpdateView.as_view()),
    path("pin/profile/otp/confirm/", PinConfirmProfileUpdateView.as_view()),
    path("pin/claims/", PinClaimsView.as_view()),
    path("pin/claims/<str:claim_id>/verify/", PinVerifyClaimView.as_view()),
    path("pin/claims/<str:claim_id>/dispute/", PinDisputeClaimView.as_view()),

    # CV
    path("cv/requests/", CvMyRequestsView.as_view()),
    path("cv/requests/<str:req_id>/complete/", CvCompleteRequestView.as_view()),
    path("cv/requests/<str:req_id>/safety_tips/", CvSafetyTipsView.as_view()),
    path("cv/requests/<str:req_id>/claims/", CvCreateClaimView.as_view()),

   #CHAT ENDPOINTS
    path("me/chats/", MyChatsView.as_view()),
    path("requests/<str:req_id>/chat/", RequestChatView.as_view()),
    path("chats/<str:chat_id>/messages/", ChatMessagesListCreate.as_view()),
    path("requests/<str:req_id>/complete/", CompleteRequestView.as_view()),

]

    

