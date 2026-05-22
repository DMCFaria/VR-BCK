from rest_framework import permissions

class IsAdminUserType(permissions.BasePermission):
    """
    Permite acesso para qualquer usuário autenticado.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated