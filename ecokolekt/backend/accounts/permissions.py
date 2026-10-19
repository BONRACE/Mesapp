from rest_framework.permissions import BasePermission

from .models import User


class _Role(BasePermission):
    roles: tuple = ()
    need_approval = True

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated and u.role in self.roles):
            return False
        return u.is_approved or not self.need_approval


class IsCitizen(_Role):
    roles = (User.Role.CITIZEN,)


class IsCollector(_Role):
    roles = (User.Role.COLLECTOR,)


class IsSeller(_Role):
    roles = (User.Role.COLLECTOR, User.Role.RECYCLER)


class IsAdminRole(_Role):
    roles = (User.Role.ADMIN,)
