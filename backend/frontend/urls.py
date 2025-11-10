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

]

