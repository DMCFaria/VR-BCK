from rest_framework import permissions

# Tipos que a equipe Fedcorp gerencia sem restrição.
TIPOS_FEDCORP = ('dev', 'fat')
# Tipos que um supervisor pode criar/editar (nunca outro sup, nem perfis Fedcorp).
TIPOS_GERENCIAVEIS_PELO_SUP = ('adm', 'dep')


class PodeGerenciarUsuarios(permissions.BasePermission):
    """
    Gerência de usuários (criar, editar, excluir, vincular administradora):

    - dev/fat: qualquer usuário, qualquer tipo.
    - sup: apenas usuários adm/dep vinculados à SUA administradora ativa.
      A restrição de tipo/administradora do payload é validada nos
      serializers e nas views (a permissão cobre o alvo, não o corpo).
    - demais tipos (adm, dep, cli, fin): sem acesso.

    Substitui a antiga IsAdminUserType, que só verificava autenticação e
    permitia a qualquer usuário se auto-promover via PATCH.
    """

    message = "Você não tem permissão para gerenciar usuários."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return getattr(user, 'tipo', None) in TIPOS_FEDCORP + ('sup',)

    def has_object_permission(self, request, view, obj):
        user = request.user
        tipo = getattr(user, 'tipo', None)

        if tipo in TIPOS_FEDCORP:
            return True

        if tipo == 'sup':
            if obj.pk == user.pk:
                # Auto-edição do sup passa (campos sensíveis são bloqueados
                # no serializer).
                return True
            if obj.tipo not in TIPOS_GERENCIAVEIS_PELO_SUP:
                return False
            adm_id = getattr(user, 'administradora_ativa_id', None)
            return bool(adm_id) and obj.administradoras.filter(id=adm_id).exists()

        return False


# Alias para não quebrar imports antigos; novo código deve usar
# PodeGerenciarUsuarios.
IsAdminUserType = PodeGerenciarUsuarios
