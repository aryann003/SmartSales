"""Role-based permissions.

Roles live on ``core.Profile.role``: admin, manager, analyst, salesperson.

Access matrix (read = GET/HEAD/OPTIONS, write = everything else):

====================  ==================  =====================================
Resource              Read                Write
====================  ==================  =====================================
Customers             any signed-in user  admin, manager, salesperson
Orders / order items  any signed-in user  admin, manager, salesperson
Returns               any signed-in user  admin, manager, salesperson
Products / categories any signed-in user  admin, manager
Analytics endpoints   admin, manager, analyst (read-only)
====================  ==================  =====================================
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission


def get_role(user):
    """Return the user's role, or None if anonymous or without a profile."""
    if not user or not user.is_authenticated:
        return None
    profile = getattr(user, "profile", None)
    return profile.role if profile else None


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return get_role(request.user) == "admin"


class IsManager(BasePermission):
    """Managers, plus admins."""

    def has_permission(self, request, view):
        return get_role(request.user) in ("admin", "manager")


class IsAnalyst(BasePermission):
    """Analysts, plus admins."""

    def has_permission(self, request, view):
        return get_role(request.user) in ("admin", "analyst")


class IsSalesperson(BasePermission):
    """Salespeople, plus admins."""

    def has_permission(self, request, view):
        return get_role(request.user) in ("admin", "salesperson")


def role_can_write(*roles):
    """Build a permission: any signed-in user may read, only ``roles`` may write.

    Admins are always allowed to write.
    """
    allowed = set(roles) | {"admin"}

    class ReadAnyWriteRoles(BasePermission):
        def has_permission(self, request, view):
            if not request.user or not request.user.is_authenticated:
                return False
            if request.method in SAFE_METHODS:
                return True
            return get_role(request.user) in allowed

    ReadAnyWriteRoles.__name__ = "ReadAnyWrite_" + "_".join(sorted(allowed))
    return ReadAnyWriteRoles


CanManageSalesData = role_can_write("manager", "salesperson")  # customers, orders, returns
CanManageCatalog = role_can_write("manager")  # products, categories


class HasAutomationKey(BasePermission):
    """Allow trusted automation callers (n8n, scheduled jobs) via a shared secret.

    The caller sends ``X-Automation-Token: <AUTOMATION_API_KEY>``. If the key is
    not configured on the server the endpoint is closed to everyone.
    """

    message = "Missing or invalid automation token."

    def has_permission(self, request, view):
        import hmac

        from django.conf import settings

        expected = settings.AUTOMATION_API_KEY
        supplied = request.headers.get("X-Automation-Token", "")
        return bool(expected) and hmac.compare_digest(supplied.encode(), expected.encode())
