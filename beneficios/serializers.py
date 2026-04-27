from rest_framework import serializers
from .models import Produto, MovimentacaoBeneficio, Importacao
from entidades.models import Condominio, Funcionario


class ProdutoSerializer(serializers.ModelSerializer):
    """
    Serializer para operações CRUD no modelo Produto (Catálogo de Benefícios).
    """
    class Meta:
        model = Produto
        fields = '__all__'
        read_only_fields = ('codigo_produto',)


class MovimentacaoBeneficioSerializer(serializers.ModelSerializer):
    """
    Serializer para operações CRUD no modelo MovimentacaoBeneficio (Transações).
    """
    class Meta:
        model = MovimentacaoBeneficio
        fields = '__all__'


class MovimentacaoSerializer(serializers.Serializer):
    produto = serializers.CharField(max_length=255)
    codigo_produto = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    valor = serializers.DecimalField(max_digits=12, decimal_places=2)


class FuncionarioSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=255)
    cpf = serializers.CharField(max_length=14)
    matricula = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    departamento = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    funcao = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    data_nascimento = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    valor_bene = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    movimentacoes = MovimentacaoSerializer(many=True)


class CondominioSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=255)
    cnpj = serializers.CharField(max_length=20)
    valor_condo = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    rua = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    numero = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    complemento = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    bairro = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cidade = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    estado = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cep = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    funcionarios = FuncionarioSerializer(many=True)


class ImportacaoListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listar histórico de importações.
    """
    nome_usuario = serializers.CharField(source='usuario.email', read_only=True)

    class Meta:
        model = Importacao
        fields = ['id', 'data_importacao', 'status', 'total_registros', 'registros_processados', 'nome_usuario', 'data_vencimento', 'vigencia_inicio', 'vigencia_fim']


class ImportacaoDetailSerializer(serializers.ModelSerializer):
    """
    Serializer detalhado para visualizar uma importação específica.
    """
    nome_usuario = serializers.CharField(source='usuario.email', read_only=True)
    nome_file = serializers.CharField(source='file_upload.file.name', read_only=True)

    class Meta:
        model = Importacao
        fields = ['id', 'file_upload', 'nome_file', 'usuario', 'nome_usuario', 'data_importacao', 'status', 'total_registros', 'registros_processados', 'erros', 'url', 'data_vencimento', 'vigencia_inicio', 'vigencia_fim']


class MovimentacaoReuseSerializer(serializers.Serializer):
    """
    Serializer para formatar movimentações no formato esperado pelo confirmed.
    """
    condominios = CondominioSerializer(many=True)