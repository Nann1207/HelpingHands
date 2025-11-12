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


def pin_dashboard_page(request): return render(request, "pin_dashboard.html")

def pin_request_detail_page(request, req_id): return render(request, "pin_request_detail.html")

def pin_profile_page(request): return render(request, "pin_profile.html")

def pin_create_request_page(request): return render(request, "pin_create_request.html")

def pin_chats_page(request): return render(request, "pin_chats.html")


@role_required("CSR")
def csr_dashboard_page(request):
    return render(request, "csr_dashboard.html")


@role_required("CSR")
def csr_requests_page(request):
    return render(request, "csr_requests.html")


@role_required("CSR")
def csr_shortlist_page(request):
    return render(request, "csr_shortlist.html")


@role_required("CSR")
def csr_match_page(request):
    return render(request, "csr_match.html")




@role_required("CSR")
def csr_claims_page(request):
    return render(request, "csr_claims.html")


@role_required("CSR")
def csr_match_detail_page(request, req_id):
    return render(request, "csr_match_detail.html", {"req_id": req_id})
