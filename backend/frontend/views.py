from django.shortcuts import render

from core.boundary.guards import role_required


def landing(request):
    return render(request, "landing.html")

def login_page(request):
    return render(request, "login.html")


@role_required("ADMIN")
def pa_dashboard_page(request):
    return render(request, "pa_dashboard.html")

@role_required("ADMIN")
def pa_flags_page(request):
    return render(request, "pa_flags.html")