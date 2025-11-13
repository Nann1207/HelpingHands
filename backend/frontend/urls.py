from django.urls import path
from . import views as pages

urlpatterns = [
    path("", pages.landing, name="landing"),
    path("login/", pages.login_page, name="login_page"),
    path("pa_dashboard/", pages.pa_dashboard_page, name="pa_dashboard_page"),
    path("pa_flags/", pages.pa_flags_page, name="pa_flags_page"),

    # --- PIN pages ---
    path("pin_dashboard/", pages.pin_dashboard_page, name="pin_dashboard_page"),
    path("pin_request/<str:req_id>/", pages.pin_request_detail_page, name="pin_request_detail_page"),
    path("pin_profile/", pages.pin_profile_page, name="pin_profile_page"),
    path("pin_create_request/", pages.pin_create_request_page, name="pin_create_request_page"),
    path("pin_chats/", pages.pin_chats_page, name="pin_chats_page"),

    # --- Corporate Social Responsibility Rep (CSR) ---
    path("csr_dashboard/", pages.csr_dashboard_page, name="csr_dashboard_page"),
    path("csr_requests/", pages.csr_requests_page, name="csr_requests_page"),
    path("csr_request/<str:req_id>/", pages.csr_request_detail_page, name="csr_request_detail_page"),
    path("csr_shortlist/", pages.csr_shortlist_page, name="csr_shortlist_page"),
    path("csr_match/", pages.csr_match_page, name="csr_match_page"),
    path("csr_claims/", pages.csr_claims_page, name="csr_claims_page"),
    path("csr_match_detail/<str:req_id>/", pages.csr_match_detail_page, name="csr_match_detail_page"),

     # --- Corporate Volunteer (CV) ---
    path("cv_dashboard/", pages.cv_dashboard_page, name="cv_dashboard_page"),
    path("cv_request/<str:req_id>/", pages.cv_request_detail_page, name="cv_request_detail_page"),
    path("cv_claims/", pages.cv_claims_page, name="cv_claims_page"),
    path("cv_chats/", pages.cv_chats_page, name="cv_chats_page"),
]
