from rest_framework import serializers
from .models import Produto, MovimentacaoBeneficio, Importacao, PedidoCartao
from entidades.models import Condominio, Funcionario


class ProdutoSerializer(serializers.ModelSerializer):
    """
    Serializer para operações CRUD no modelo Produto (Catálogo de Benefícios).
    """
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)

    class Meta:
        model = Produto
        fields = [
            'codigo_produto',
            'nome',
            'tipo',
            'tipo_display',
            'fornecedora',
            'cod_fornecedora',
        ]
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
    valor = serializers.DecimalField(max_digits=15, decimal_places=2)

class FuncionarioSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=255)
    cpf = serializers.CharField(max_length=14)
    matricula = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    departamento = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    funcao = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    data_nascimento = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    cep = serializers.CharField(max_length=10, required=False, allow_null=True, allow_blank=True)
    endereco_rua = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    endereco_numero = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)
    endereco_complemento = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)
    endereco_bairro = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)
    valor_bene = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    
    movimentacoes = MovimentacaoSerializer(many=True, required=False)
    
    def to_internal_value(self, data):
        modified_data = data.copy()

        if 'beneficios' in modified_data and modified_data['beneficios']:
            modified_data['movimentacoes'] = modified_data.pop('beneficios')

        return super().to_internal_value(modified_data)
    
    def validate(self, data):
        # Garante que pelo menos um dos dois exista
        if not data.get('movimentacoes') and not data.get('beneficios'):
            raise serializers.ValidationError({
                "movimentacoes": "É necessário informar movimentacoes ou beneficios"
            })
        return data

class CondominioSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=255)
    cnpj = serializers.CharField(max_length=20)
    valor_condo = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
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
    nome_administradora = serializers.CharField(source='administradora.razao_social', read_only=True)
  

    class Meta:
        model = Importacao
        fields = ['id', 'data_importacao','nome_administradora', 'status', 'total_registros', 'registros_processados', 'nome_usuario', 'data_vencimento', 'vigencia_inicio', 'vigencia_fim', 'arquivo_s3', 'arquivo_s3_editado']

class ImportacaoDetailSerializer(serializers.ModelSerializer):
    """
    Serializer detalhado para visualizar uma importação específica.
    """
    nome_usuario = serializers.CharField(source='usuario.email', read_only=True)
    nome_file = serializers.CharField(source='file_upload.file.name', read_only=True)

    class Meta:
        model = Importacao
        fields = ['id', 'file_upload', 'nome_file', 'usuario', 'nome_usuario', 'data_importacao', 'status', 'total_registros', 'registros_processados', 'erros', 'arquivo_s3', 'arquivo_s3_editado', 'data_vencimento', 'data_recebimento', 'vigencia_inicio', 'vigencia_fim']

class ImportacaoComMovimentacoesSerializer(serializers.ModelSerializer):
    nome_usuario = serializers.CharField(source='usuario.email', read_only=True)
    responsavel_nome = serializers.SerializerMethodField(read_only=True)

    def get_responsavel_nome(self, obj):
        if obj.responsavel:
            return obj.responsavel.nome or obj.responsavel.email
        return None

    valor_total = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    total_funcionarios = serializers.IntegerField(required=False)
    nome_administradora = serializers.CharField(source='administradora.razao_social', read_only=True)
    class Meta:
        model = Importacao
        fields = [
            'id',
            'data_importacao',
            'status',
            'total_registros',
            'nome_administradora',
            'registros_processados',
            'nome_usuario',
            'responsavel',
            'responsavel_nome',
            'data_vencimento',
            'data_recebimento',
            'vigencia_inicio',
            'vigencia_fim',
            'valor_total',
            'total_funcionarios',
            'modelo_importacao',
            'arquivo_s3',
            'arquivo_s3_editado'
        ]

class MovimentacaoReuseSerializer(serializers.Serializer):
    """
    Serializer para formatar movimentações no formato esperado pelo confirmed.
    """
    condominios = CondominioSerializer(many=True)


class PedidoCartaoSerializer(serializers.ModelSerializer):
    administradora_nome = serializers.CharField(source='administradora.nome_fantasia', read_only=True)
    criado_por_nome = serializers.CharField(source='criado_por.username', read_only=True)
    tipo_pedido_display = serializers.CharField(source='get_tipo_pedido_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = PedidoCartao
        fields = [
            'id', 'tipo_pedido', 'tipo_pedido_display',
            'nome_completo', 'cpf', 'data_nascimento',
            'produto', 'nome_condominio',
            'cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'estado',
            'valor',
            'status', 'status_display', 'observacao',
            'administradora', 'administradora_nome',
            'criado_por', 'criado_por_nome',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status', 'administradora', 'criado_por', 'created_at', 'updated_at']