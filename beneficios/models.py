from django.db import models
from entidades.models import Condominio, Funcionario
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


class Importacao(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pendente'),
        ('PROCESSING', 'Processando'),
        ('COMPLETED', 'Concluída'),
        ('FAILED', 'Falhou'),
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
    data_importacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data da Importação"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name="Status"
    )
    total_registros = models.IntegerField(default=0, verbose_name="Total de Registros")
    registros_processados = models.IntegerField(default=0, verbose_name="Registros Processados")
    erros = models.JSONField(default=list, verbose_name="Erros")
    url = models.URLField(max_length=500, verbose_name="URL", null=True, blank=True)

    class Meta:
        verbose_name = "Importação"
        verbose_name_plural = "Importações"
        ordering = ['-data_importacao']

    def __str__(self):
        return f"Importação #{self.id} - {self.data_importacao.strftime('%d/%m/%Y %H:%M')}"


# Modelo PRODUTO (Catálogo de Benefícios)
class Produto(models.Model):
    codigo_produto = models.CharField(
        max_length=50, # Aumentado por segurança
        primary_key=True, 
        verbose_name="Código do Produto"
    )
    nome = models.CharField(max_length=255, verbose_name="Nome do Produto/Benefício")

    class Meta:
        verbose_name = "Produto/Benefício"
        verbose_name_plural = "Produtos/Benefícios"

    def __str__(self):
        return f"{self.nome} ({self.codigo_produto})"


# Modelo MOVIMENTACAO_BENEFICIO (Tabela de Fatos)
class MovimentacaoBeneficio(models.Model):
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

    # Dados da Transação
    data_competencia = models.DateField(verbose_name="Data de Competência")
    valor_beneficio = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name="Valor do Benefício"
    )
    quantidade_dias = models.IntegerField(verbose_name="Quantidade", default=0)

    class Meta:
        verbose_name = "Movimentação de Benefício"
        verbose_name_plural = "Movimentações de Benefício"
        
        # Unicidade para não duplicar lançamento no mesmo mês
        unique_together = (
            'empresa_cnpj', 
            'funcionario_cpf', 
            'produto_codigo', 
            'data_competencia'
        )

    def __str__(self):
        return f"{self.produto_codigo} - {self.funcionario_cpf} ({self.data_competencia})"