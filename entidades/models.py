from django.db import models


class Administradora(models.Model):
    TIPO_TAXA_CHOICES = [
        ('PERC', 'Percentual (%)'),
        ('FIXO', 'Valor Fixo (R$)'),
    ]

    cnpj = models.CharField(max_length=20, unique=True, verbose_name="CNPJ")
    razao_social = models.CharField(max_length=255, verbose_name="Nome/Razão Social")
    nome_fantasia = models.CharField(max_length=255, verbose_name="Nome Fantasia", null=True, blank=True)
    email = models.EmailField(verbose_name="E-mail", blank=True, null=True)
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    
    cartao_admin = models.BooleanField(default=True, verbose_name="Cartão Admin")

    endereco = models.CharField(max_length=255, verbose_name="Endereço (Rua)", blank=True, null=True)
    numero = models.CharField(max_length=20, verbose_name="Número", blank=True, null=True)
    complemento = models.CharField(max_length=100, verbose_name="Complemento", blank=True, null=True)
    bairro = models.CharField(max_length=100, verbose_name="Bairro", blank=True, null=True)
    cidade = models.CharField(max_length=100, verbose_name="Cidade", blank=True, null=True)
    estado = models.CharField(max_length=2, verbose_name="Estado (UF)", blank=True, null=True)
    cep = models.CharField(max_length=10, verbose_name="CEP", blank=True, null=True)

    valor_max_beneficio = models.DecimalField(
        max_digits=10, decimal_places=2, default=9999.99,
        verbose_name="Valor máximo por funcionário"
    )

    d_mais = models.PositiveSmallIntegerField(
        default=3,
        verbose_name="D+"
    )

    # Taxa padrão da administradora
    taxa_padrao_tipo = models.CharField(
        max_length=4,
        choices=TIPO_TAXA_CHOICES,
        default='PERC',
        verbose_name="Tipo da Taxa Padrão"
    )
    taxa_padrao_valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Valor da Taxa Padrão"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Administradora"
        verbose_name_plural = "Administradoras"
        ordering = ['razao_social']

    def __str__(self):
        return f"{self.razao_social} ({self.cnpj})"


class Gerente(models.Model):
    nome = models.CharField(max_length=255, verbose_name="Nome Completo")
    email = models.EmailField(verbose_name="E-mail", blank=True, null=True)
    telefone = models.CharField(max_length=20, verbose_name="Telefone", blank=True, null=True)
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Gerente"
        verbose_name_plural = "Gerentes"
        ordering = ['nome']

    def __str__(self):
        return self.nome


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
    gerentes = models.ManyToManyField(
        Gerente,
        blank=True,
        verbose_name="Gerentes",
        related_name='vinculos'
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
        return f"{self.administradora.razao_social} - {self.condominio.nome}"


class TaxaConfig(models.Model):
    TIPO_TAXA_CHOICES = [
        ('PERC', 'Percentual (%)'),
        ('FIXO', 'Valor Fixo (R$)'),
    ]
    # Replica das escolhas do modelo Produto para evitar importação circular.
    TIPO_PRODUTO_CHOICES = [
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

    vinculo = models.ForeignKey(
        VinculoCondominio,
        on_delete=models.CASCADE,
        verbose_name="Vínculo",
        related_name='taxas_config'
    )
    produto = models.ForeignKey(
        'beneficios.Produto',
        on_delete=models.CASCADE,
        verbose_name="Produto",
        null=True,
        blank=True,
        help_text="Se vazio, aplica a todos os produtos deste vínculo"
    )
    tipo = models.CharField(
        max_length=30,
        choices=TIPO_PRODUTO_CHOICES,
        null=True,
        blank=True,
        verbose_name="Tipo do Produto",
        help_text="Se preenchido, aplica a todos os produtos deste tipo"
    )
    taxa_tipo = models.CharField(
        max_length=4,
        choices=TIPO_TAXA_CHOICES,
        default='PERC',
        verbose_name="Tipo da Taxa"
    )
    taxa_valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Valor da Taxa"
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração de Taxa"
        verbose_name_plural = "Configurações de Taxas"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['vinculo', 'produto'],
                condition=models.Q(produto__isnull=False),
                name='unique_vinculo_produto'
            ),
            models.UniqueConstraint(
                fields=['vinculo', 'tipo'],
                condition=models.Q(tipo__isnull=False),
                name='unique_vinculo_tipo'
            ),
            models.UniqueConstraint(
                fields=['vinculo'],
                condition=models.Q(produto__isnull=True, tipo__isnull=True),
                name='unique_vinculo_geral'
            ),
        ]

    def __str__(self):
        if self.tipo:
            alvo = f"Tipo: {self.get_tipo_display()}"
        elif self.produto:
            alvo = self.produto.nome
        else:
            alvo = "Todos os produtos"
        return f"{self.vinculo} - {alvo} ({self.get_taxa_tipo_display()})"


class Condominio(models.Model):
    cnpj = models.CharField(
        max_length=20,
        primary_key=True,
        verbose_name="CNPJ"
    )
    nome = models.CharField(max_length=255, verbose_name="Razão Social / Departamento")
    tipo_local = models.CharField(max_length=50, verbose_name="Tipo de Local", default="CONDOMINIO")
    is_searched = models.BooleanField(default=False, verbose_name="Pesquisado")
    
    endereco = models.CharField(max_length=255, verbose_name="Endereço (Rua)", blank=True, null=True)
    numero = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número")
    complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Complemento")
    bairro = models.CharField(max_length=100, verbose_name="Bairro", blank=True, null=True)
    cidade = models.CharField(max_length=100, verbose_name="Cidade", blank=True, null=True)
    estado = models.CharField(max_length=2, verbose_name="Estado (UF)", blank=True, null=True)
    cep = models.CharField(max_length=10, verbose_name="CEP", blank=True, null=True)

    is_searched = models.BooleanField(
        default=False,
        verbose_name="Endereço pesquisado automaticamente",
        help_text="Indica se o endereço já foi preenchido via consulta automática de CNPJ."
    )

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
    
    condominio = models.ForeignKey(
        'Condominio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Condomínio",
        related_name='funcionarios'
    )
    
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
    
    telefone = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    email = models.EmailField(
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = "Funcionário"
        verbose_name_plural = "Funcionários"
        indexes = [
            models.Index(fields=['condominio'], name='idx_func_condo'),
        ]

    def __str__(self):
        return f"{self.nome} ({self.cpf})"
