from django.db import models
from entidades.models import Condominio, Funcionario

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