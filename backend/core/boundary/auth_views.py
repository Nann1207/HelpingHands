# core/boundary/auth_views.py
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse, HttpResponseRedirect
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required

def _infer_role(user):
    if hasattr(user, "pa"):
        return "ADMIN"
    if hasattr(user, "csrrep"):
        return "CSR"
    if hasattr(user, "cv"):
        return "CV"
    if hasattr(user, "personinneed"):
        return "PIN"
    return "UNKNOWN"

@csrf_protect
@require_POST
def auth_login(request):
    # expects form POST with 'username' and 'password'
    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "").strip()

    user = authenticate(request, username=username, password=password)
    if not user:
        # If you post from an HTML form, this JSON is fine (or redirect back with a message)
        return JsonResponse({"detail": "Invalid credentials"}, status=401)

    login(request, user)  # sets session cookie

    role = _infer_role(user)
    redirect_to = {
        "ADMIN": "/pa_dashboard/",
        "CSR":   "/csr/home/",
        "CV":    "/cv/home/",
        "PIN":   "/pin/home/",
    }.get(role, "/")

    return HttpResponseRedirect(redirect_to)

@login_required
def auth_me(request):
    u = request.user
    role = _infer_role(u)
    return JsonResponse({
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": role,
        "is_authenticated": True,
    })

@require_POST
@login_required
def auth_logout(request):
    logout(request)
    return HttpResponseRedirect("/login/")
