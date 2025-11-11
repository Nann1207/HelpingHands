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
    PinClaimsView, PinVerifyClaimView, PinDisputeClaimView,PinChangePasswordView, PinStartPasswordOTPView
)

from .csr_views import ( 
    CSRAdvanceQueueView, CSRCreateQueueView, CSRFlagRequestView,  CSRPendingRequestsView, 
    CSRShortlistsView, CSRMatchSuggestionsView, CSRStartQueueView, MyNotificationsView, MarkAllNotificationsReadView, MarkNotificationReadView)

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

# ----- PIN -----
    path("pin/requests/",            PinRequestCreateView.as_view(),     name="pin-requests-create"),   
    path("pin/my/requests/",         PinMyRequestsView.as_view(),        name="pin-requests-list"),     
    path("pin/profile/otp/start/",   PinStartProfileUpdateView.as_view(), name="pin-profile-otp-start"),
    path("pin/profile/otp/confirm/", PinConfirmProfileUpdateView.as_view(), name="pin-profile-otp-confirm"),
    path("pin/password/otp/start/", PinStartPasswordOTPView.as_view(), name="pin-password-otp-start"),
    path("pin/password/change/", PinChangePasswordView.as_view(), name="pin-password-change"),
    path("pin/claims/",              PinClaimsView.as_view(),            name="pin-claims-list"),
    path("pin/claims/<str:claim_id>/verify/",  PinVerifyClaimView.as_view(),  name="pin-claim-verify"),
    path("pin/claims/<str:claim_id>/dispute/", PinDisputeClaimView.as_view(), name="pin-claim-dispute"),

    # ----- CV -----
    path("cv/requests/",                      CvMyRequestsView.as_view(),       name="cv-requests-list"),
    path("cv/requests/<str:req_id>/complete/", CvCompleteRequestView.as_view(), name="cv-request-complete"),
    path("cv/requests/<str:req_id>/safety_tips/", CvSafetyTipsView.as_view(),   name="cv-request-safety"),
    path("cv/requests/<str:req_id>/claims/",     CvCreateClaimView.as_view(),   name="cv-request-claims"),

    # ----- Chat -----
    path("me/chats/",                    MyChatsView.as_view(),            name="me-chats"),
    path("requests/<str:req_id>/chat/",  RequestChatView.as_view(),        name="request-chat"),
    path("chats/<str:chat_id>/messages/", ChatMessagesListCreate.as_view(), name="chat-messages"),
    path("requests/<str:req_id>/complete/", CompleteRequestView.as_view(),  name="request-complete"),



    # CSR core routes
    path("csr/requests/pending/", CSRPendingRequestsView.as_view(), name="csr-requests-pending"),
    path("csr/shortlists/", CSRShortlistsView.as_view(), name="csr-shortlists"),
    path("csr/requests/<str:req_id>/flag/", CSRFlagRequestView.as_view(), name="csr-flag-request"),

    # suggestions + queue
    path("csr/requests/<str:req_id>/suggestions/", CSRMatchSuggestionsView.as_view(), name="csr-match-suggestions"),
    path("csr/requests/<str:req_id>/queue/", CSRCreateQueueView.as_view(), name="csr-create-queue"),
    path("csr/requests/<str:req_id>/queue/start/", CSRStartQueueView.as_view(), name="csr-start-queue"),
    path("csr/requests/<str:req_id>/queue/advance/", CSRAdvanceQueueView.as_view(), name="csr-advance-queue"),

    # notifications
    path("me/notifications/", MyNotificationsView.as_view(), name="me-notifications"),
    path("me/notifications/mark_all_read/", MarkAllNotificationsReadView.as_view(), name="me-notifications-mark-all"),
    path("me/notifications/<int:notif_id>/read/", MarkNotificationReadView.as_view(), name="me-notifications-read"),




]


    

