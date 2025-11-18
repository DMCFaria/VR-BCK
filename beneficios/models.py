from django.db import models
from django.core.validators import MinLengthValidator
from entidades.models import Condominio, Funcionario # Importa os modelos de entidades

# Modelo PRODUTO (Catálogo de Benefícios - Chave Principal: Codigo do Produto)
class Produto(models.Model):
    # PK: codigo_produto (usado como chave primária)
    codigo_produto = models.CharField(
        max_length=15, 
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
    # FKs: Chaves Estrangeiras para as entidades
    empresa_cnpj = models.ForeignKey(
        Condominio, 
        on_delete=models.CASCADE, 
        db_column='empresa_cnpj', 
        verbose_name="Condomínio CNPJ"
    )
    funcionario_cpf = models.ForeignKey(
        Funcionario, 
        on_delete=models.CASCADE, 
        db_column='funcionario_cpf', 
        verbose_name="Funcionário CPF"
    )
    produto_codigo = models.ForeignKey(
        Produto, 
        on_delete=models.CASCADE, 
        db_column='produto_codigo',
        verbose_name="Produto Código"
    )

    # Dados da Transação
    data_competencia = models.DateField(verbose_name="Data de Competência (MM/AAAA)")
    valor_beneficio = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Valor do Benefício"
    )
    quantidade_dias = models.IntegerField(verbose_name="Quantidade de Dias/Unidades")

    class Meta:
        verbose_name = "Movimentação de Benefício"
        verbose_name_plural = "Movimentações de Benefício"
        
        # Restrição de Unicidade Composta:
        # Garante que um registro seja único para a mesma empresa, funcionário, produto, na mesma competência.
        unique_together = (
            'empresa_cnpj', 
            'funcionario_cpf', 
            'produto_codigo', 
            'data_competencia'
        )

    def __str__(self):
        return f"Movimentação de {self.produto_codigo} para {self.funcionario_cpf} ({self.data_competencia})"