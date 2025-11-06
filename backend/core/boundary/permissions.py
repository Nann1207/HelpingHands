from rest_framework.permissions import BasePermission

class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if getattr(user, "is_staff", False):
            return True
        return hasattr(user, "pa")