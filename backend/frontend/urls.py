from django.urls import path
from . import views as pages

urlpatterns = [
    path("", pages.landing, name="landing"),
    path("login/", pages.login_page, name="login_page"),
    path("pa_dashboard/", pages.pa_dashboard_page, name="pa_dashboard_page"),
    path("pa_flags/", pages.pa_flags_page, name="pa_flags_page"),
]
