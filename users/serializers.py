from rest_framework import serializers
from .models import CustomUser

class CustomUserSerializer(serializers.ModelSerializer):
    """
    Serializador para visualização e atualização de dados do usuário (exceto senha).
    """
    class Meta:
        model = CustomUser
        fields = (
            'id', 
            'email', 
            'username', 
            'first_name', 
            'last_name', 
            'empresa', 
            'tipo',
            'created_at'
        )
        read_only_fields = ('email', 'created_at', 'tipo')


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializador para registro de novos usuários.
    """
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = CustomUser
        fields = ('email', 'username', 'password', 'password2', 'tipo', 'empresa')
        extra_kwargs = {
            'username': {'required': True},
            'tipo': {'required': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Os campos de senha não coincidem."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = CustomUser.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password'],
            tipo=validated_data.get('tipo', 'adm'), 
            empresa=validated_data.get('empresa', ''),
        )
        return user