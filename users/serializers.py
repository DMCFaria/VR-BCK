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
        fields = ['id', 'username', 'nome', 'email', 'password', 'tipo', 'administradora']
        extra_kwargs = {
            'password': {'write_only': True},
            'administradora': {'required': False, 'allow_null': True},
            'username': {'required': False},
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
        fields = ['id', 'nome', 'email', 'tipo', 'administradora', 'administradora_id', 'administradora_nome', 'created_at', 'updated_at', 'primeiro_acesso']
        read_only_fields = ['id', 'created_at', 'updated_at', 'primeiro_acesso']
        extra_kwargs = {
            'username': {'required': False}, 
            'email': {'required': False},   
            'tipo': {'required': False},  
        }
    
    def update(self, instance, validated_data):
        # Tratamento especial para senha
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        
        # Atualizar administradora 
        administradora = validated_data.pop('administradora', None)
        if administradora is not None:  # Se veio no payload, atualizar
            instance.administradora = administradora
        
        # Atualizar outros campos apenas se presentes
        for attr, value in validated_data.items():
            if value is not None: 
                setattr(instance, attr, value)
        
        instance.save()
        return instance