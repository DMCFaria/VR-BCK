from rest_framework import serializers
from .models import Condominio, Funcionario, Administradora, VinculoCondominio, Gerente, TaxaConfig


class CondominioSerializer(serializers.ModelSerializer):
    administradoras = serializers.SerializerMethodField(read_only=True)

    def validate_cnpj(self, value):
        cnpj = ''.join(filter(str.isdigit, str(value)))

        if not cnpj:
            raise serializers.ValidationError('CNPJ obrigatório.')

        if len(cnpj) != 14:
            raise serializers.ValidationError('CNPJ inválido.')

        return cnpj

    def get_administradoras(self, obj):
        vinculos = getattr(obj, 'vinculocondominio_set', None)
        if vinculos is None:
            return []
        return [
            {
                'id': v.administradora_id,
                'nome': v.administradora.razao_social,
            }
            for v in vinculos.all()
        ]

    class Meta:
        model = Condominio
        fields = '__all__'

class FuncionarioSerializer(serializers.ModelSerializer):

    def validate_cpf(self, value):
        cpf = ''.join(filter(str.isdigit, str(value)))

        if not cpf:
            raise serializers.ValidationError('CPF obrigatório.')

        if len(cpf) != 11:
            raise serializers.ValidationError('CPF inválido.')

        return cpf

    class Meta:
        model = Funcionario
        fields = '__all__'

class AdministradoraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Administradora
        fields = [
            'id', 'cnpj', 'razao_social', 'nome_fantasia', 'email', 'ativo',
            'cartao_admin', 'd_mais',
            'taxa_padrao_tipo', 'taxa_padrao_valor',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate_cartao_admin(self, value):
        """Valida se cartao_admin é booleano"""
        if not isinstance(value, bool):
            raise serializers.ValidationError('cartao_admin deve ser true ou false')
        return value
    
    def validate_valor_max_beneficio(self, value):
        """Valida se o valor máximo é positivo"""
        if value is not None and value <= 0:
            raise serializers.ValidationError('O valor máximo deve ser maior que zero')
        return value
    
class RegraValorSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    administradora_id = serializers.IntegerField(source='id', read_only=True)
    ativo = serializers.BooleanField()
    valor_limite = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    bloquear_acima_limite = serializers.BooleanField()
    d_mais = serializers.IntegerField(required=False)
    
    def validate(self, data):
        """Validações cruzadas"""
        ativo = data.get('ativo')
        valor_limite = data.get('valor_limite')
        
        if ativo and (valor_limite is None or valor_limite <= 0):
            raise serializers.ValidationError({
                'valor_limite': 'Quando ativa, a regra deve ter um valor limite válido (> 0)'
            })
        
        return data

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
    taxas_config = serializers.SerializerMethodField(read_only=True)

    def get_taxas_config(self, obj):
        taxas = obj.taxas_config.all()
        return TaxaConfigSerializer(taxas, many=True).data

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
            'taxas_config',
            'created_at'
        ]
        read_only_fields = ['created_at']


class TaxaConfigSerializer(serializers.ModelSerializer):
    vinculo_display = serializers.SerializerMethodField(read_only=True)
    produto_nome = serializers.CharField(source='produto.nome', read_only=True, default=None)
    produto_codigo = serializers.CharField(source='produto.codigo_produto', read_only=True, default=None)

    def get_vinculo_display(self, obj):
        return str(obj.vinculo)

    class Meta:
        model = TaxaConfig
        fields = [
            'id',
            'vinculo',
            'vinculo_display',
            'produto',
            'produto_nome',
            'produto_codigo',
            'taxa_tipo',
            'taxa_valor',
            'ativo',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
