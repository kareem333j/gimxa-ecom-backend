from rest_framework.permissions import BasePermission

class AdminPermission(BasePermission):
    """
    Allow access only to admin users.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
            and request.user.is_superuser
        )

def is_admin_user(request):
    user = request.user
    return bool(user and user.is_authenticated and user.is_superuser)
    
class IsOwnerOrAdmin(BasePermission):
    """
    Allow access if user is admin or owner of the object.
    """

    owner_fields = ["user", "owner", "created_by"]

    def has_object_permission(self, request, view, obj):
        # Admin
        if request.user and request.user.is_superuser:
            return True

        # Check common owner fields
        for field in self.owner_fields:
            if hasattr(obj, field):
                owner = getattr(obj, field)
                if owner == request.user:
                    return True

        return False