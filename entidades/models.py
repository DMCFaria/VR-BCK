from django.db import models
from django.core.validators import MinLengthValidator

# Modelo CONDOMINIO (Chave Principal: CNPJ)
class Condominio(models.Model):
    cnpj = models.CharField(
        max_length=20, # Aumentado para garantir compatibilidade com formatações
        primary_key=True,
        verbose_name="CNPJ"
    )
    nome = models.CharField(max_length=255, verbose_name="Razão Social / Departamento")
    tipo_local = models.CharField(max_length=50, verbose_name="Tipo de Local", default="CONDOMINIO")
    
    # Endereço
    endereco = models.CharField(max_length=255, verbose_name="Endereço (Rua)", blank=True, null=True)
    numero = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número")
    complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Complemento")
    bairro = models.CharField(max_length=100, verbose_name="Bairro", blank=True, null=True)
    cidade = models.CharField(max_length=100, verbose_name="Cidade", blank=True, null=True)
    estado = models.CharField(max_length=2, verbose_name="Estado (UF)", blank=True, null=True)
    cep = models.CharField(max_length=10, verbose_name="CEP", blank=True, null=True)

    class Meta:
        verbose_name = "Condomínio"
        verbose_name_plural = "Condomínios"

    def __str__(self):
        return f"{self.nome} ({self.cnpj})"


# Modelo FUNCIONARIO (Chave Principal: CPF)
class Funcionario(models.Model):
    cpf = models.CharField(
        max_length=14, # Aumentado para 14 para caber formatação se houver
        primary_key=True,
        verbose_name="CPF"
    )
    # Matricula não deve ser Unique globalmente, pois empresas diferentes podem ter matriculas iguais
    matricula = models.CharField(
        max_length=50, 
        verbose_name="Matrícula",
        blank=True, 
        null=True
    )
    nome = models.CharField(max_length=255, verbose_name="Nome Completo")
    
    # Campo adicionado para corrigir o erro "Invalid field name 'departamento'"
    departamento = models.CharField(max_length=255, verbose_name="Departamento / Local", blank=True, null=True)
    
    funcao = models.CharField(max_length=100, verbose_name="Função/Cargo", blank=True, null=True)
    data_nascimento = models.DateField(verbose_name="Data de Nascimento", blank=True, null=True)
    
    # Campos opcionais que podem não vir no layout simplificado
    sexo = models.CharField(max_length=1, verbose_name="Sexo", blank=True, null=True)
    mae = models.CharField(max_length=255, verbose_name="Nome da Mãe", blank=True, null=True)
    
    # Endereço
    cep = models.CharField(max_length=10, verbose_name="CEP", blank=True, null=True)
    endereco_rua = models.CharField(max_length=255, verbose_name="Rua", blank=True, null=True)
    endereco_numero = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número")
    endereco_complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Complemento")
    endereco_bairro = models.CharField(max_length=100, verbose_name="Bairro", blank=True, null=True)

    class Meta:
        verbose_name = "Funcionário"
        verbose_name_plural = "Funcionários"

    def __str__(self):
        return f"{self.nome} ({self.cpf})"