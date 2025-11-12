# core/boundary/auth_views.py
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse, HttpResponseRedirect
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

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
@require_POST #Only allow POST requests
def auth_login(request):
    # expects form POST with 'username' and 'password'
    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "").strip()

    user = authenticate(request, username=username, password=password)
    if not user:
        #Returns 401 Unauthorized if authentication fails
        return JsonResponse({"detail": "Invalid credentials"}, status=401)

    login(request, user)  # sets session cookie

    #Redirects the user’s browser there.
    role = _infer_role(user)
    redirect_to = {
        "ADMIN": "/pa_dashboard/",
        "CSR":   "/csr_dashboard/",
        "CV":    "/cv_dashboard/",
        "PIN":   "/pin_dashboard/",
    }.get(role, "/")

    return HttpResponseRedirect(redirect_to)

#This is useful for the frontend to know who is logged in and what role to show
@login_required
def auth_me(request):
    u = request.user  # get the currently logged-in user

    # Determine role dynamically
    role = (
        "pa" if hasattr(u, "pa") else
        "csr" if hasattr(u, "csrrep") else
        "cv" if hasattr(u, "cv") else
        "pin" if hasattr(u, "personinneed") else
        "user"
    )

    # Base user data
    data = {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": role,
        "is_authenticated": True,
    }

    
    if role == "pin":
        pin = u.personinneed
        data.update({
            "pin_id": pin.id,
            "name": pin.name,
            "phone": pin.phone,
            "address": pin.address,
            "preferred_cv_gender": pin.preferred_cv_gender,
            "preferred_cv_language": pin.preferred_cv_language,
            "dob": pin.dob.isoformat() if pin.dob else None,
        })

    return JsonResponse(data, status=200)




@require_POST
@login_required
def auth_logout(request):
    logout(request)
    return HttpResponseRedirect("/login/")
