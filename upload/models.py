from django.db import models
from users.models import CustomUser

class FileUpload(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pendente de Processamento'),
        ('PARSED', 'Dados Extraídos, Pendente de Confirmação'),
        ('AGUARDANDO_FATURAMENTO', 'Aguardando Faturamento'),
        ('COMPLETED', 'Processamento Finalizado'),
        ('FAILED', 'Falha no Processamento')
    )

    file = models.FileField(null=True, blank=True) 
    
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, default=1, verbose_name="Enviado por") 
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    process_status = models.CharField(
        max_length=30, 
        choices=STATUS_CHOICES, 
        default='PENDING',
        verbose_name="Status do Processamento"
    )
    summary_data = models.JSONField(blank=True, null=True) 

    class Meta:
        verbose_name = "Upload de Arquivo"
        verbose_name_plural = "Uploads de Arquivos"

    def __str__(self):
        return f"Arquivo {self.file.name} - Status: {self.get_process_status_display()}"