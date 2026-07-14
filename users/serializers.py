# users/serializers.py
from rest_framework import serializers
from .models import CustomUser
from entidades.models import Administradora

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
