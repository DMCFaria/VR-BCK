from django.db import models
from django.core.validators import MinLengthValidator

# Modelo CONDOMINIO (Chave Principal: CNPJ)
class Condominio(models.Model):
    # PK: CNPJ (usado como chave primária)
    cnpj = models.CharField(
        max_length=14, 
        primary_key=True,
        validators=[MinLengthValidator(14)],
        verbose_name="CNPJ"
    )
    nome = models.CharField(max_length=255, verbose_name="Nome do Condomínio")
    tipo_local = models.CharField(max_length=50, verbose_name="Tipo de Local")
    
    # Endereço
    endereco = models.CharField(max_length=255, verbose_name="Endereço (Rua)")
    numero = models.CharField(max_length=10, blank=True, null=True, verbose_name="Número")
    complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Complemento")
    bairro = models.CharField(max_length=100, verbose_name="Bairro")
    cidade = models.CharField(max_length=100, verbose_name="Cidade")
    estado = models.CharField(max_length=2, verbose_name="Estado")
    cep = models.CharField(max_length=8, verbose_name="CEP")

    class Meta:
        verbose_name = "Condomínio"
        verbose_name_plural = "Condomínios"

    def __str__(self):
        return f"{self.nome} ({self.cnpj})"

# Modelo FUNCIONARIO (Chave Principal: CPF)
class Funcionario(models.Model):
    # PK: CPF (usado como chave primária)
    cpf = models.CharField(
        max_length=11,
        primary_key=True,
        validators=[MinLengthValidator(11)],
        verbose_name="CPF"
    )
    matricula = models.CharField(
        max_length=20, 
        unique=True, 
        verbose_name="Matrícula"
    ) # Unique, mas não a PK
    nome = models.CharField(max_length=255, verbose_name="Nome Completo")
    funcao = models.CharField(max_length=100, verbose_name="Função/Cargo")
    data_nascimento = models.DateField(verbose_name="Data de Nascimento")
    sexo = models.CharField(max_length=1, verbose_name="Sexo")
    mae = models.CharField(max_length=255, verbose_name="Nome da Mãe")
    
    # Endereço (Mantido no modelo, pois o funcionário é a entidade primária)
    cep = models.CharField(max_length=8, verbose_name="CEP")
    endereco_rua = models.CharField(max_length=255, verbose_name="Rua")
    endereco_numero = models.CharField(max_length=10, blank=True, null=True, verbose_name="Número")
    endereco_complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Complemento")
    endereco_bairro = models.CharField(max_length=100, verbose_name="Bairro")

    class Meta:
        verbose_name = "Funcionário"
        verbose_name_plural = "Funcionários"

    def __str__(self):
        return f"{self.nome} ({self.cpf})"