# users/serializers.py
from rest_framework import serializers
from .models import CustomUser
from entidades.models import Administradora

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    administradora = serializers.PrimaryKeyRelatedField(
        queryset=Administradora.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'password', 'tipo', 'administradora']
        extra_kwargs = {
            'password': {'write_only': True},
            'administradora': {'required': False, 'allow_null': True}
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        administradora = validated_data.pop('administradora', None)
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.administradora = administradora
        user.save()
        return user


class CustomUserSerializer(serializers.ModelSerializer):
    administradora_id = serializers.IntegerField(source='administradora.id', read_only=True)
    administradora_nome = serializers.CharField(source='administradora.razao_social', read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'tipo', 'administradora', 'administradora_id', 'administradora_nome', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def update(self, instance, validated_data):
        # Tratamento especial para senha
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        
        # Atualizar administradora (pode ser None para desvincular)
        administradora = validated_data.pop('administradora', None)
        if administradora is not None:
            instance.administradora = administradora
        
        # Atualizar outros campos
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance