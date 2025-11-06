# core/boundary/guards.py
from functools import wraps
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required

def role_required(*allowed):
    def deco(view):
        @login_required
        @wraps(view)
        def _w(request, *a, **kw):
            u = request.user
            role = ("ADMIN" if hasattr(u, "pa")
                    else "CSR" if hasattr(u, "csrrep")
                    else "CV" if hasattr(u, "cv")
                    else "PIN" if hasattr(u, "personinneed")
                    else "UNKNOWN")
            if role not in allowed:
                return HttpResponseForbidden("Forbidden")
            return view(request, *a, **kw)
        return _w
    return deco
