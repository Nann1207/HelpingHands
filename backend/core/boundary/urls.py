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

from core.boundary.cv_views import (
    CvDashboardView, CvOfferDecisionView,
    CvMyRequestsView, CvRequestDetailView,
    CvSafetyTipsView, CvCompleteRequestView,
    CvCreateClaimView, CvMyClaimsView,
)

# PIN
from .pin_views import (
    PinRequestCreateView, PinMyRequestsView,
    PinStartProfileUpdateView, PinConfirmProfileUpdateView,
    PinClaimsView, PinVerifyClaimView, PinDisputeClaimView,PinChangePasswordView, PinStartPasswordOTPView
)

from .csr_views import ( 
    CSRDashboardView, CSRRequestPoolView, CSRRequestDetailView, CSRRequestFlagView, CSRShortlistToggleView,
    CSRCommitFromPoolView, CSRShortlistView, CSRCommitListView,
    CSRMatchSuggestView, CSRMatchAssignmentPoolView, CSRSendOffersView,
    CVCandidateDecisionView, DormantSweepView,
    CSRNotificationsView, CSRCompletedView, CSRCompletedClaimsView,
    CSRClaimDecisionView,
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
    path("cv/dashboard/",                        CvDashboardView.as_view(),     name="cv-dashboard"),
    path("cv/requests/",                         CvMyRequestsView.as_view(),    name="cv-requests-list"),
    path("cv/requests/<str:req_id>/",            CvRequestDetailView.as_view(), name="cv-request-detail"),
    path("cv/requests/<str:req_id>/decision/",   CvOfferDecisionView.as_view(), name="cv-request-decision"),
    path("cv/requests/<str:req_id>/complete/",   CvCompleteRequestView.as_view(), name="cv-request-complete"),
    path("cv/requests/<str:req_id>/safety_tips/", CvSafetyTipsView.as_view(),   name="cv-request-safety"),
    path("cv/requests/<str:req_id>/claims/",     CvCreateClaimView.as_view(),   name="cv-request-claims"),
    path("cv/claims/",                           CvMyClaimsView.as_view(),      name="cv-claims"),

    # ----- Chat -----
    path("me/chats/",                    MyChatsView.as_view(),            name="me-chats"),
    path("requests/<str:req_id>/chat/",  RequestChatView.as_view(),        name="request-chat"),
    path("chats/<str:chat_id>/messages/", ChatMessagesListCreate.as_view(), name="chat-messages"),
    path("requests/<str:req_id>/complete/", CompleteRequestView.as_view(),  name="request-complete"),



    path("csr/dashboard/", CSRDashboardView.as_view()),
    path("csr/requests/", CSRRequestPoolView.as_view()),
    path("csr/requests/<str:request_id>/", CSRRequestDetailView.as_view()),
    path("csr/requests/<str:request_id>/flag/", CSRRequestFlagView.as_view()),
    path("csr/requests/<str:request_id>/shortlist/", CSRShortlistToggleView.as_view()),
    path("csr/requests/<str:request_id>/commit/", CSRCommitFromPoolView.as_view()),

    path("csr/shortlist/", CSRShortlistView.as_view()),
    path("csr/committed/", CSRCommitListView.as_view()),

    path("csr/match/<str:request_id>/suggest/", CSRMatchSuggestView.as_view()),
    path("csr/match/<str:request_id>/assignment/", CSRMatchAssignmentPoolView.as_view()),
    path("csr/match/<str:request_id>/send_offers/", CSRSendOffersView.as_view()),
    path("csr/match/<str:request_id>/cv/<str:cv_id>/decision/", CVCandidateDecisionView.as_view()),
    path("csr/match/sweep_dormant/", DormantSweepView.as_view()),

    path("csr/notifications/", CSRNotificationsView.as_view()),

    path("csr/completed/", CSRCompletedView.as_view()),
    path("csr/completed/<str:request_id>/claims/", CSRCompletedClaimsView.as_view()),
    path("csr/claims/<str:claim_id>/decision/", CSRClaimDecisionView.as_view()),
]
