from django.db import models
from django.conf import settings


class Fatura(models.Model):
    STATUS_CHOICES = [
        ('faturado', 'Faturado'),
        ('atrasado', 'Confirmar Pagamento'),
        ('aprovado', 'Boleto VR Enviado'),
        ('pago', 'Pago'),
    ]

    fatura_num = models.CharField(max_length=100, verbose_name="Número da Fatura")
    emissao = models.DateField(verbose_name="Data de Emissão", null=True, blank=True)
    estipulante_nome = models.CharField(max_length=255, verbose_name="Nome do Estipulante")
    estipulante_cnpj = models.CharField(max_length=20, verbose_name="CNPJ do Estipulante", blank=True, default='')
    administradora_nome = models.CharField(max_length=255, verbose_name="Nome da Administradora", blank=True, default='')
    uploader_name = models.CharField(max_length=255, verbose_name="Responsável", blank=True, default='')
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Responsável",
        related_name='faturas_operacionais'
    )
    manual_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        null=True, blank=True,
        verbose_name="Status Manual"
    )
    total_cents = models.IntegerField(default=0, verbose_name="Total em Centavos")
    arquivo_pdf = models.FileField(upload_to='operacional/faturas/', blank=True, null=True, verbose_name="Arquivo PDF")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Fatura"
        verbose_name_plural = "Faturas"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.fatura_num} - {self.estipulante_nome}"


class CoEstipulante(models.Model):
    fatura = models.ForeignKey(
        Fatura,
        on_delete=models.CASCADE,
        related_name='co_estipulantes',
        verbose_name="Fatura"
    )
    nome = models.CharField(max_length=255, verbose_name="Nome")
    cnpj = models.CharField(max_length=20, verbose_name="CNPJ", blank=True, default='')
    valor_cents = models.IntegerField(default=0, verbose_name="Valor em Centavos")
    due_date = models.DateField(verbose_name="Data de Vencimento", null=True, blank=True)
    data_credito = models.DateField(verbose_name="Data de Crédito", null=True, blank=True)
    paid_at = models.DateTimeField(verbose_name="Data de Pagamento", null=True, blank=True)
    sent_to_cp = models.BooleanField(default=False, verbose_name="Enviado para Contas a Pagar")
    forma_pagamento = models.CharField(max_length=50, verbose_name="Forma de Pagamento", blank=True, null=True)

    class Meta:
        verbose_name = "Co-Estipulante"
        verbose_name_plural = "Co-Estipulantes"
        ordering = ['id']

    def __str__(self):
        return f"{self.nome} ({self.cnpj})"


class Boleto(models.Model):
    name = models.CharField(max_length=255, verbose_name="Nome")
    file_name = models.CharField(max_length=255, verbose_name="Nome do Arquivo", blank=True, default='')
    due_date = models.DateField(verbose_name="Data de Vencimento", null=True, blank=True)
    value_cents = models.IntegerField(default=0, verbose_name="Valor em Centavos")
    paid_at = models.DateTimeField(verbose_name="Data de Pagamento", null=True, blank=True)
    uploader_name = models.CharField(max_length=255, verbose_name="Responsável", blank=True, default='')
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Responsável",
        related_name='boletos_operacionais'
    )
    arquivo = models.FileField(upload_to='operacional/boletos/', blank=True, null=True, verbose_name="Arquivo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Boleto"
        verbose_name_plural = "Boletos"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.due_date}"


class FaturaComment(models.Model):
    fatura = models.ForeignKey(
        Fatura,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name="Fatura"
    )
    text = models.TextField(verbose_name="Texto")
    image_data = models.TextField(verbose_name="Imagem (base64)", blank=True, null=True)
    author_name = models.CharField(max_length=255, verbose_name="Autor", blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Comentário da Fatura"
        verbose_name_plural = "Comentários das Faturas"
        ordering = ['-created_at']

    def __str__(self):
        return f"Comment by {self.author_name} on {self.fatura}"
