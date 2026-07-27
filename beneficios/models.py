from django.db import models
from entidades.models import Condominio, Funcionario
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


class Importacao(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pendente'),
        ('PROCESSING', 'Processando'),
        ('AGUARDANDO_FATURAMENTO', 'Aguardando Faturamento'),
        ('FATURADO', 'Faturado'),
        ('CONFIRMAR_PAGAMENTO', 'Confirmar Pagamento'),
        ('BOLETO_VR_ENVIADO', 'Boleto VR Enviado'),
        ('PAGO', 'Pago'),
        ('COMPRADO', 'Comprado'),
        ('PAGO_PARCIALMENTE', 'Pago Parcialmente'),
        ('CANCELADO', 'Cancelado'),
        ('COMPLETED', 'Concluída'),
        ('FAILED', 'Falhou'),
    ]

    MODEL_CHOICES = [
        ('VR-BENEFICIOS', 'VR Benefícios'),
        ('VT-AUTO', 'VT Auto'),
        ('OUTRO', 'Outro')
    ]

    id = models.AutoField(primary_key=True, verbose_name="ID")
    file_upload = models.ForeignKey(
        'upload.FileUpload',
        on_delete=models.CASCADE,
        verbose_name="Arquivo Carregado",
        null=True,
        blank=True
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        verbose_name="Usuário",
        null=True,
        blank=True
    )
    administradora = models.ForeignKey(
        'entidades.Administradora',
        on_delete=models.SET_NULL,
        verbose_name="Administradora",
        null=True,
        blank=True,
        related_name='importacoes'
    )
    data_importacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data da Importação"
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True,
        verbose_name="Status"
    )
    total_funcionarios = models.IntegerField(default=0, verbose_name="Total de Registros")
    total_registros = models.IntegerField(default=0, verbose_name="Total de Registros")
    registros_processados = models.IntegerField(default=0, verbose_name="Registros Processados")
    erros = models.JSONField(default=list, verbose_name="Erros")
    arquivo_s3 = models.CharField(max_length=500, blank=True, null=True, verbose_name="Arquivo S3")
    arquivo_s3_editado = models.CharField(max_length=500, blank=True, null=True, verbose_name="Arquivo S3 Editado")
    data_vencimento = models.DateField(verbose_name="Data de Vencimento", null=True, blank=True)
    data_recebimento = models.DateField(verbose_name="Data de Recebimento", null=True, blank=True)
    vigencia_inicio = models.DateField(verbose_name="Início da Vigência", null=True, blank=True)
    vigencia_fim = models.DateField(verbose_name="Fim da Vigência", null=True, blank=True)
    
    modelo_importacao = models.CharField(
        max_length=20,
        choices=MODEL_CHOICES,
        verbose_name="Modelo de Importação",
    )

    valor_total = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0, 
        verbose_name="Valor Total da Importação"
    )

    class Meta:
        verbose_name = "Importação"
        verbose_name_plural = "Importações"
        ordering = ['-data_importacao']
        indexes = [
            models.Index(fields=['administradora', 'status'], name='idx_importacao_adm_status'),
            models.Index(fields=['administradora', '-data_importacao'], name='idx_importacao_adm_data'),
        ]

    def __str__(self):
        return f"Importação #{self.id} - {self.data_importacao.strftime('%d/%m/%Y %H:%M')}"

# Modelo PRODUTO (Catálogo de Benefícios)
class Produto(models.Model):
    TIPO_CHOICES = [
        ('ALIMENTACAO', 'Alimentação'),
        ('AUTO', 'Auto'),
        ('REFEICAO', 'Refeição'),
        ('MULTI_HOME_OFFICE', 'Multi - Home Office'),
        ('BOAS_FESTAS', 'Boas Festas'),
        ('MULTI_ALIMENTACAO', 'Multi - Alimentação'),
        ('MULTI_VR_VA', 'Multi - VR+VA'),
        ('MULTI_REFEICAO', 'Multi - Refeição'),
        ('MULTI_MOBILIDADE', 'Multi - Mobilidade'),
    ]
    FORNECEDORA_CHOICES = [
        ('VR', 'VR'),
        ('TICKET', 'Ticket'),
        ('OUTRO', 'Outro')
    ]

    codigo_produto = models.CharField(
        max_length=50, # Aumentado por segurança
        primary_key=True, 
        verbose_name="Código do Produto"
    )
    nome = models.CharField(max_length=255, verbose_name="Nome do Produto/Benefício")
    tipo = models.CharField(
        max_length=30,
        choices=TIPO_CHOICES,
        blank=True,
        null=True,
        verbose_name="Tipo do Produto"
    )
    fornecedora = models.CharField(
        max_length=20,
        choices=FORNECEDORA_CHOICES,
        verbose_name="Fornecedora",
        default="VR"
    )
    cod_fornecedora = models.CharField(max_length=50, verbose_name="Código da Fornecedora", default='000000')

    class Meta:
        verbose_name = "Produto/Benefício"
        verbose_name_plural = "Produtos/Benefícios"

    def __str__(self):
        return f"{self.nome} ({self.codigo_produto})"

    def get_tipo_display_or_codigo(self):
        return self.get_tipo_display() if self.tipo else self.codigo_produto

# Modelo MOVIMENTACAO_BENEFICIO (Tabela de Fatos)
# Modelo FATURAMENTO (Processamento e Geração de Documentos)
class Faturamento(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pendente'),
        ('PROCESSING', 'Processando'),
        ('COMPLETED', 'Concluído'),
        ('FATURADO', 'Faturado'),
        ('FAILED', 'Falhou'),
    ]

    importacao = models.ForeignKey(
        Importacao,
        on_delete=models.CASCADE,
        related_name='faturamentos',
        verbose_name="Importação"
    )
    administradora = models.ForeignKey(
        'entidades.Administradora',
        on_delete=models.CASCADE,
        verbose_name="Administradora",
        null=True,
        blank=True,
        related_name='faturamentos'
    )
    competencia = models.DateField(verbose_name="Competência (Mês/Ano)")
    arquivo_unificado_url = models.URLField(max_length=500, verbose_name="URL Arquivo Unificado", null=True, blank=True)
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Criado por"
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="Status")
    progresso = models.PositiveSmallIntegerField(default=0, verbose_name="Progresso (%)")

    class Meta:
        verbose_name = "Faturamento"
        verbose_name_plural = "Faturamentos"
        ordering = ['-criado_em']

    def __str__(self):
        return f"Faturamento #{self.id} - {self.competencia}"

# Modelo FATURAMENTO_DOCUMENTO (Documentos Gerados no Faturamento)
class FaturamentoDocumento(models.Model):
    faturamento = models.ForeignKey(
        Faturamento,
        on_delete=models.CASCADE,
        related_name='documentos',
        verbose_name="Faturamento"
    )
    condominio = models.ForeignKey(
        Condominio,
        on_delete=models.CASCADE,
        related_name='documentos_faturamento',
        verbose_name="Condomínio"
    )
    url_boleto = models.URLField(max_length=500, verbose_name="URL Boleto")
    url_nota_debito = models.URLField(max_length=500, verbose_name="URL Nota Débito")
    url_nota_fiscal = models.URLField(max_length=500, verbose_name="URL Nota Fiscal", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Documento de Faturamento"
        verbose_name_plural = "Documentos de Faturamento"
        unique_together = ('faturamento', 'condominio')

    def __str__(self):
        return f"{self.condominio.cnpj} - {self.faturamento.id}"




class MovimentacaoBeneficio(models.Model):
    
    fat_status = models.CharField(
        max_length=30,
        choices=Faturamento.STATUS_CHOICES,
        null=True,
        blank=True,
        verbose_name="Status do Faturamento"
    )
    
    # Relacionamentos
    empresa_cnpj = models.ForeignKey(
        Condominio, 
        on_delete=models.CASCADE, 
        verbose_name="Condomínio"
    )
    funcionario_cpf = models.ForeignKey(
        Funcionario, 
        on_delete=models.CASCADE, 
        verbose_name="Funcionário"
    )
    produto_codigo = models.ForeignKey(
        Produto, 
        on_delete=models.CASCADE,
        verbose_name="Produto"
    )
    importacao = models.ForeignKey(
        Importacao,
        on_delete=models.SET_NULL,
        verbose_name="Importação",
        null=True,
        blank=True,
        related_name='movimentacoes'
    )
    importacao_status = models.CharField(
        max_length=30,
        choices=Importacao.STATUS_CHOICES,
        verbose_name="Status da Importação"
    )

    # Dados da Transação
    data_competencia = models.DateField(db_index=True, verbose_name="Data de Competência")
    valor_beneficio = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name="Valor do Benefício"
    )
    quantidade_dias = models.IntegerField(verbose_name="Quantidade", default=0)

    class Meta:
        verbose_name = "Movimentação de Benefício"
        verbose_name_plural = "Movimentações de Benefício"
        
        # Unicidade: permite mesmo combo em importações diferentes
        unique_together = (
            'importacao',
            'empresa_cnpj', 
            'funcionario_cpf', 
            'produto_codigo', 
            'data_competencia'
        )

    def __str__(self):
        return f"{self.produto_codigo} - {self.funcionario_cpf} ({self.data_competencia})"


class Boleto(models.Model):
    faturamento = models.ForeignKey(
        Faturamento,
        on_delete=models.CASCADE,
        related_name='boletos_rel',
        verbose_name="Faturamento",
        null=True,
        blank=True
    )
    documento = models.CharField(max_length=100, verbose_name="Documento", null=True, blank=True, unique=True)
    dt_emissao = models.DateField(verbose_name="Data de Emissão", null=True, blank=True)
    fatura = models.CharField(max_length=100, verbose_name="Fatura", null=True, blank=True)
    codigo_de_barra = models.CharField(max_length=255, verbose_name="Código de Barra", null=True, blank=True)
    qr_code = models.TextField(verbose_name="QR Code", null=True, blank=True)
    qr_imagem = models.TextField(verbose_name="QR Imagem", null=True, blank=True)
    vencimento = models.DateField(verbose_name="Vencimento", null=True, blank=True)
    nome_cobrado = models.CharField(max_length=255, verbose_name="Nome Cobrado", null=True, blank=True)
    cnpj_cobrado = models.CharField(max_length=50, verbose_name="CNPJ Cobrado", null=True, blank=True)
    cedente = models.CharField(max_length=255, verbose_name="Cedente", null=True, blank=True)
    cnpj_cedente = models.CharField(max_length=50, verbose_name="CNPJ do Cedente", null=True, blank=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor", null=True, blank=True)
    deducoes = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Deduções", null=True, blank=True)
    status = models.CharField(max_length=50, verbose_name="Status", null=True, blank=True)
    nosso_numero = models.CharField(max_length=100, verbose_name="Nosso Número", null=True, blank=True)
    identificador = models.CharField(max_length=100, verbose_name="Identificador", null=True, blank=True)
    baixa = models.BooleanField(default=False, verbose_name="Baixa")
    dt_baixa = models.DateField(verbose_name="Data da Baixa", null=True, blank=True)
    obs_baixa = models.TextField(verbose_name="Observação da Baixa", null=True, blank=True)
    NFs_id = models.CharField(max_length=100, verbose_name="NFs ID", null=True, blank=True, unique=True)
    Numero_nota = models.CharField(max_length=50, verbose_name="Número da Nota", null=True, blank=True, unique=True)
    url_nota = models.URLField(max_length=500, verbose_name="URL da Nota", null=True, blank=True, unique=True)
    match = models.BooleanField(default=False, verbose_name="Match")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Boleto"
        verbose_name_plural = "Boletos"
        ordering = ['-vencimento']

    def __str__(self):
        return f"Boleto #{self.id} - Fatura: {self.fatura} - Vencimento: {self.vencimento}"


class PedidoCartao(models.Model):
    TIPO_CHOICES = [
        ('NOVO', 'Cartão Novo'),
        ('SEGUNDA_VIA', 'Segunda Via'),
    ]
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('EM_ANALISE', 'Em Análise'),
        ('APROVADO', 'Aprovado'),
        ('ENVIADO', 'Enviado'),
        ('RECUSADO', 'Recusado'),
        ('CANCELADO', 'Cancelado'),
    ]

    id = models.AutoField(primary_key=True)
    criado_por = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Criado por"
    )
    administradora = models.ForeignKey(
        'entidades.Administradora',
        on_delete=models.CASCADE,
        verbose_name="Administradora"
    )

    tipo_pedido = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo de Pedido")
    nome_completo = models.CharField(max_length=255, verbose_name="Nome Completo")
    cpf = models.CharField(max_length=14, verbose_name="CPF")
    data_nascimento = models.DateField(verbose_name="Data de Nascimento")
    produto = models.CharField(max_length=100, verbose_name="Produto")
    nome_condominio = models.CharField(max_length=255, verbose_name="Nome do Condomínio")
    cep = models.CharField(max_length=10, verbose_name="CEP", blank=True, null=True)
    logradouro = models.CharField(max_length=255, verbose_name="Logradouro", blank=True, null=True)
    numero = models.CharField(max_length=20, verbose_name="Número", blank=True, null=True)
    complemento = models.CharField(max_length=100, verbose_name="Complemento", blank=True, null=True)
    bairro = models.CharField(max_length=100, verbose_name="Bairro", blank=True, null=True)
    cidade = models.CharField(max_length=100, verbose_name="Cidade", blank=True, null=True)
    estado = models.CharField(max_length=2, verbose_name="UF", blank=True, null=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor", blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDENTE',
        verbose_name="Status"
    )
    observacao = models.TextField(blank=True, null=True, verbose_name="Observação")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Pedido de Cartão"
        verbose_name_plural = "Pedidos de Cartão"
        ordering = ['-created_at']

    def __str__(self):
        return f"Pedido #{self.id} - {self.nome_completo} - {self.get_tipo_pedido_display()}"
