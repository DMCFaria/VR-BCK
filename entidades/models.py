from django.db import models
from django.core.validators import MinLengthValidator


class Administradora(models.Model):
    cnpj = models.CharField(max_length=20, unique=True, verbose_name="CNPJ")
    nome = models.CharField(max_length=255, verbose_name="Nome/Razão Social")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Administradora"
        verbose_name_plural = "Administradoras"
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.cnpj})"


class VinculoCondominio(models.Model):
    administradora = models.ForeignKey(
        Administradora,
        on_delete=models.CASCADE,
        verbose_name="Administradora"
    )
    condominio = models.ForeignKey(
        'Condominio',
        on_delete=models.CASCADE,
        verbose_name="Condomínio"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Vínculo de Condomínio"
        verbose_name_plural = "Vínculos de Condomínios"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['administradora', 'condominio'],
                name='unique_administradora_condominio'
            )
        ]

    def __str__(self):
        return f"{self.administradora.nome} - {self.condominio.nome}"


class Condominio(models.Model):
    cnpj = models.CharField(
        max_length=20,
        primary_key=True,
        verbose_name="CNPJ"
    )
    nome = models.CharField(max_length=255, verbose_name="Razão Social / Departamento")
    tipo_local = models.CharField(max_length=50, verbose_name="Tipo de Local", default="CONDOMINIO")
    
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


class Funcionario(models.Model):
    cpf = models.CharField(
        max_length=14,
        primary_key=True,
        verbose_name="CPF"
    )
    matricula = models.CharField(
        max_length=50, 
        verbose_name="Matrícula",
        blank=True, 
        null=True
    )
    nome = models.CharField(max_length=255, verbose_name="Nome Completo")
    
    departamento = models.CharField(max_length=255, verbose_name="Departamento / Local", blank=True, null=True)
    
    funcao = models.CharField(max_length=100, verbose_name="Função/Cargo", blank=True, null=True)
    data_nascimento = models.DateField(verbose_name="Data de Nascimento", blank=True, null=True)
    
    sexo = models.CharField(max_length=1, verbose_name="Sexo", blank=True, null=True)
    mae = models.CharField(max_length=255, verbose_name="Nome da Mãe", blank=True, null=True)
    
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
