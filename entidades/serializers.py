from rest_framework import serializers
from .models import Condominio, Funcionario, Administradora, VinculoCondominio, Gerente


class CondominioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Condominio
        fields = '__all__'
        read_only_fields = ('cnpj',)


class FuncionarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Funcionario
        fields = '__all__'
        read_only_fields = ('cpf',)


class AdministradoraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Administradora
        fields = ['id', 'cnpj', 'nome', 'ativo', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class GerenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gerente
        fields = ['id', 'nome', 'email', 'telefone', 'ativo', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class VinculoCondominioSerializer(serializers.ModelSerializer):
    condominio_nome = serializers.CharField(source='condominio.nome', read_only=True)
    condominio_cnpj = serializers.CharField(source='condominio.cnpj', read_only=True)
    administradora_nome = serializers.CharField(source='administradora.nome', read_only=True)
    administradora_cnpj = serializers.CharField(source='administradora.cnpj', read_only=True)
    gerentes_detalhes = GerenteSerializer(source='gerentes', many=True, read_only=True)

    class Meta:
        model = VinculoCondominio
        fields = [
            'id',
            'condominio',
            'condominio_nome',
            'condominio_cnpj',
            'administradora',
            'administradora_nome',
            'administradora_cnpj',
            'gerentes',
            'gerentes_detalhes',
            'created_at'
        ]
        read_only_fields = ['created_at']
