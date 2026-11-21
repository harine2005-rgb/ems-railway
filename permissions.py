from rest_framework.permissions import BasePermission


def get_role(user):
    """Return 'Admin', 'HR', 'Employee' or None."""

    if not user or not user.is_authenticated:
        return None

    if user.is_superuser or user.is_staff:
        return 'Admin'

    if user.groups.filter(name='HR').exists():
        return 'HR'

    if hasattr(user, 'employee_profile'):
        return 'Employee'

    return None


class HasRole(BasePermission):
    """Any logged-in user who has a role."""

    def has_permission(self, request, view):
        return get_role(request.user) is not None


class IsStaffRole(BasePermission):
    """Admin or HR."""

    def has_permission(self, request, view):
        return get_role(request.user) in ('Admin', 'HR')


class IsAdminRole(BasePermission):
    """Admin only."""

    def has_permission(self, request, view):
        return get_role(request.user) == 'Admin'