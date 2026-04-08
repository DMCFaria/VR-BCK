from rest_framework import permissions

class IsAdminUserType(permissions.BasePermission):
    """
    Permissão customizada para permitir acesso apenas a usuários com o campo 
    'tipo' igual a 'dev' (Desenvolvedor) ou 'fin' (Financeiro).
    """
    
    # Tipos de usuário que terão permissão para acessar a rota
    ALLOWED_TYPES = ["dev", "fin"]

    def has_permission(self, request, view):
        # 1. Verifica se o usuário está autenticado
        if not request.user.is_authenticated:
            # Se não estiver autenticado, nega o acesso imediatamente
            return False

        # 2. Verifica se o tipo do usuário está na lista de tipos permitidos
        user_type = request.user.tipo
        
        # Garante que o usuário tem o campo 'tipo' e que ele está entre os tipos permitidos
        return user_type in self.ALLOWED_TYPES