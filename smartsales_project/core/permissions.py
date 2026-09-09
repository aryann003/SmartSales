from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    def has_permission(self,request,view):
        return hasattr(request.user, 'profile') and request.user.profile.role == 'admin'


class IsManager(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'profile') and request.user.profile.role in['admin', 'manager']


class IsAnalyst(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'profile') and request.user.profile.role in['admin','analyst']

class IsSalesperson(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'profile') and request.user.profile.rolw in['admin','salesperson']

    
