from rest_framework import serializers
from .models import Condominio, Funcionario

class CondominioSerializer(serializers.ModelSerializer):
    """
    Serializer para operações CRUD no modelo Condominio.
    """
    class Meta:
        model = Condominio
        fields = '__all__'
        read_only_fields = ('cnpj',) # CNPJ é a chave primária e pode ser read-only após a criação

class FuncionarioSerializer(serializers.ModelSerializer):
    """
    Serializer para operações CRUD no modelo Funcionario.
    """
    class Meta:
        model = Funcionario
        fields = '__all__'
        read_only_fields = ('cpf',) # CPF é a chave primária e pode ser read-only após a criação