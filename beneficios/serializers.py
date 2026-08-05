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
    numero_fatura = serializers.SerializerMethodField(read_only=True)
    documentos = serializers.SerializerMethodField(read_only=True)
    competencia = serializers.SerializerMethodField(read_only=True)
    data_credito = serializers.SerializerMethodField(read_only=True)
    boletos_pagamento = serializers.SerializerMethodField(read_only=True)

    def get_responsavel_nome(self, obj):
        if obj.responsavel:
            return obj.responsavel.nome or obj.responsavel.email
        return None

    def get_numero_fatura(self, obj):
        try:
            boleto = obj.faturamentos.values_list('boletos_rel__fatura', flat=True).exclude(
                boletos_rel__fatura__isnull=True
            ).exclude(
                boletos_rel__fatura=''
            ).first()
            return boleto or ''
        except Exception:
            return ''

    def _get_fatura_number(self, fat):
        try:
            boleto = fat.boletos_rel.exclude(fatura__isnull=True).exclude(fatura='').first()
            return boleto.fatura if boleto else ''
        except Exception:
            return ''

    def get_competencia(self, obj):
        """
        Competência (mês/ano de referência) vinda do Faturamento.

        Antes esse campo não era exposto, e o frontend caía no fallback
        `vigencia_inicio` — exibindo a vigência sob o rótulo "Competência".
        """
        try:
            for faturamento in obj.faturamentos.all():
                if faturamento.competencia:
                    return faturamento.competencia
            return None
        except Exception:
            return None

    def get_data_credito(self, obj):
        """
        Data de crédito = data de recebimento do benefício (`Importacao.data_recebimento`),
        escolhida pelo cliente no momento da importação da planilha
        (ver `upload/serializers.py`, campo `data_recebimento` / alias
        `recebimento_beneficio`).

        Alias explícito de `data_recebimento`: o rótulo de negócio é
        "Data de Crédito" e o `ColaboradorDashboard` já exibia esse campo com
        esse nome. Mantido como `data_credito` porque `KanbanFaturasView` e
        `FaturasTable.jsx` também consomem esse nome.

        NÃO é derivado de `Boleto.dt_baixa` — a baixa é o pagamento do boleto
        pela administradora, evento distinto do crédito do benefício. O status
        de pagamento por boleto está em `get_boletos_pagamento()`.
        """
        return obj.data_recebimento

    def get_boletos_pagamento(self, obj):
        """
        Situação de pagamento dos boletos da importação, para detalhar quem já
        teve o crédito liberado e quem está pendente.

        Retorna contagens agregadas + a lista por boleto. Depende do prefetch
        de `faturamentos__boletos_rel` em `ImportacaoListView`.
        """
        try:
            itens = []
            for faturamento in obj.faturamentos.all():
                for boleto in faturamento.boletos_rel.all():
                    pago = bool(boleto.baixa)
                    itens.append({
                        'id': boleto.id,
                        'condominio': boleto.nome_cobrado or '',
                        'cnpj': boleto.cnpj_cobrado or '',
                        'fatura': boleto.fatura or '',
                        'valor': float(boleto.valor) if boleto.valor is not None else None,
                        'vencimento': boleto.vencimento,
                        'pago': pago,
                        'data_pagamento': boleto.dt_baixa if pago else None,
                    })

            # Pendentes primeiro (é o que exige ação), depois por condomínio.
            itens.sort(key=lambda item: (item['pago'], item['condominio']))

            pagos = sum(1 for item in itens if item['pago'])
            return {
                'total': len(itens),
                'pagos': pagos,
                'pendentes': len(itens) - pagos,
                'itens': itens,
            }
        except Exception:
            return {'total': 0, 'pagos': 0, 'pendentes': 0, 'itens': []}

    def get_documentos(self, obj):
        faturamentos = list(obj.faturamentos.all())
        if not faturamentos:
            return []

        todos_arquivos = []
        for fat in faturamentos:
            arquivos = list(fat.arquivos_originais.all())
            fatura_num = self._get_fatura_number(fat)
            if arquivos:
                todos_arquivos.extend([
                    {
                        'id': arquivo.id,
                        'tipo': arquivo.tipo,
                        'tipo_display': arquivo.get_tipo_display(),
                        'nome_arquivo': arquivo.nome_arquivo,
                        'url': arquivo.url,
                        'fatura_id': fat.id,
                        'numero_fatura': arquivo.fatura_num or fatura_num,
                        'criado_em': arquivo.criado_em,
                    }
                    for arquivo in arquivos
                ])
            else:
                for documento in fat.documentos.select_related('condominio').all():
                    dados_condominio = {
                        'condominio_nome': documento.condominio.nome if documento.condominio else '',
                        'condominio_cnpj': documento.condominio.cnpj if documento.condominio else '',
                    }
                    for tipo, url, label in (
                        ('boleto', documento.url_boleto, 'Boleto'),
                        ('nota_debito', documento.url_nota_debito, 'Nota de débito'),
                        ('nota_fiscal', documento.url_nota_fiscal, 'Nota fiscal'),
                    ):
                        if url:
                            todos_arquivos.append({
                                **dados_condominio,
                                'tipo': tipo,
                                'tipo_display': label,
                                'nome_arquivo': label,
                                'url': url,
                                'fatura_id': fat.id,
                                'numero_fatura': fatura_num,
                            })
        return todos_arquivos

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
            'competencia',
            'data_credito',
            'boletos_pagamento',
            'vigencia_inicio',
            'vigencia_fim',
            'valor_total',
            'total_funcionarios',
            'modelo_importacao',
            'arquivo_s3',
            'arquivo_s3_editado',
            'numero_fatura',
            'documentos',
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
