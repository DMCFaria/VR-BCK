# users/serializers.py
from rest_framework import serializers
from .models import CustomUser
from .permissions import TIPOS_FEDCORP, TIPOS_GERENCIAVEIS_PELO_SUP
from entidades.models import Administradora


def _requisitante(serializer):
    request = serializer.context.get('request')
    return getattr(request, 'user', None)


def _validar_alvo_para_sup(requisitante, tipo_alvo, administradoras_alvo):
    """
    Regras do supervisor ao criar/editar usuários:
    só tipos adm/dep e só vínculos com a própria administradora.
    Levanta ValidationError quando violado.
    """
    if tipo_alvo and tipo_alvo not in TIPOS_GERENCIAVEIS_PELO_SUP:
        raise serializers.ValidationError({
            'tipo': 'Supervisor só pode criar/editar usuários dos tipos adm e dep.'
        })
    if administradoras_alvo:
        proprias = set(requisitante.administradoras.values_list('id', flat=True))
        pedidas = {a.id if hasattr(a, 'id') else int(a) for a in administradoras_alvo}
        if not pedidas.issubset(proprias):
            raise serializers.ValidationError({
                'administradoras': 'Supervisor só pode vincular usuários à própria administradora.'
            })


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    administradoras = serializers.PrimaryKeyRelatedField(
        queryset=Administradora.objects.all(),
        many=True,
        required=False,
        allow_empty=True
    )

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'nome', 'email', 'password', 'tipo', 'administradoras']
        extra_kwargs = {
            'password': {'write_only': True},
            'username': {'required': False},
        }

    def validate(self, data):
        user = _requisitante(self)
        tipo_requisitante = getattr(user, 'tipo', None)
        if tipo_requisitante in TIPOS_FEDCORP:
            return data
        if tipo_requisitante == 'sup':
            _validar_alvo_para_sup(user, data.get('tipo'), data.get('administradoras'))
            return data
        raise serializers.ValidationError('Você não tem permissão para criar usuários.')

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        administradoras = validated_data.pop('administradoras', [])
        username = validated_data.get('username')
        if username:
            validated_data.setdefault('nome', username)
            validated_data.setdefault('first_name', username)
        user = CustomUser(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        if administradoras:
            user.administradoras.set(administradoras)
            if not user.administradora_ativa and administradoras:
                user.administradora_ativa = administradoras[0]
                user.save(update_fields=['administradora_ativa'])
        return user

class CustomUserSerializer(serializers.ModelSerializer):
    administradora_id = serializers.IntegerField(source='administradora_ativa_id', read_only=True)
    administradora_nome = serializers.CharField(source='administradora_ativa.razao_social', read_only=True)
    administradoras_data = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            'id', 'nome', 'email', 'tipo',
            'administradoras', 'administradora_ativa',
            'administradora_id', 'administradora_nome', 'administradoras_data',
            'created_at', 'updated_at', 'primeiro_acesso',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'primeiro_acesso']
        extra_kwargs = {
            'username': {'required': False},
            'email': {'required': False},
            'tipo': {'required': False},
            'administradoras': {'required': False},
            'administradora_ativa': {'required': False, 'allow_null': True},
        }

    def get_administradoras_data(self, obj):
        admins = obj.administradoras.all()
        return [
            {'id': a.id, 'razao_social': a.razao_social, 'nome_fantasia': a.nome_fantasia}
            for a in admins
        ]

    def validate(self, data):
        # Só valida em escrita com instância (updates); criação usa o
        # UserRegistrationSerializer.
        if not self.instance:
            return data

        user = _requisitante(self)
        tipo_requisitante = getattr(user, 'tipo', None)

        if tipo_requisitante in TIPOS_FEDCORP:
            return data

        campos_sensiveis = {'tipo', 'administradoras', 'administradora_ativa'}
        alterando_sensiveis = campos_sensiveis & set(data.keys())

        if tipo_requisitante == 'sup':
            if user and self.instance.pk == user.pk:
                # Auto-edição: sup não muda o próprio tipo/vínculos.
                if alterando_sensiveis:
                    raise serializers.ValidationError(
                        'Você não pode alterar seu próprio tipo ou vínculos.'
                    )
                return data
            _validar_alvo_para_sup(user, data.get('tipo'), data.get('administradoras'))
            if 'administradora_ativa' in data and data['administradora_ativa'] is not None:
                if data['administradora_ativa'].id not in set(
                    user.administradoras.values_list('id', flat=True)
                ):
                    raise serializers.ValidationError({
                        'administradora_ativa': 'Supervisor só pode usar a própria administradora.'
                    })
            return data

        # Demais perfis (adm, dep, cli, fin): só auto-edição de campos não
        # sensíveis (a CurrentUserView usa este serializer).
        if user and self.instance.pk == user.pk:
            if 'tipo' in data or 'administradoras' in data:
                raise serializers.ValidationError(
                    'Você não pode alterar seu próprio tipo ou vínculos.'
                )
            if 'administradora_ativa' in data and data['administradora_ativa'] is not None:
                if data['administradora_ativa'].id not in set(
                    user.administradoras.values_list('id', flat=True)
                ):
                    raise serializers.ValidationError({
                        'administradora_ativa': 'Administradora fora dos seus vínculos.'
                    })
            return data

        raise serializers.ValidationError('Você não tem permissão para editar usuários.')

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)

        administradoras = validated_data.pop('administradoras', None)
        administradora_ativa = validated_data.pop('administradora_ativa', None)

        if administradoras is not None:
            instance.administradoras.set(administradoras)

        if administradora_ativa is not None:
            instance.administradora_ativa = administradora_ativa

        for attr, value in validated_data.items():
            if value is not None:
                setattr(instance, attr, value)

        instance.save()
        return instance
