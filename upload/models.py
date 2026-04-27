from django.db import models
from users.models import CustomUser

class FileUpload(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pendente de Processamento'),
        ('PARSED', 'Dados Extraídos, Pendente de Confirmação'),
        ('COMPLETED', 'Processamento Finalizado'),
        ('FAILED', 'Falha no Processamento')
    )

    file = models.FileField() 
    
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, default=1, verbose_name="Enviado por") 
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    process_status = models.CharField(
        max_length=10, 
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

class ProcessedFile(models.Model):
    id = models.BigAutoField(primary_key=True)
    file = models.ForeignKey(FileUpload, on_delete=models.CASCADE, verbose_name="Arquivo Original")
    processed_at = models.DateTimeField(auto_now_add=True, verbose_name="Processado em")
    processed_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="Processado por")
    dados_requisicao = models.JSONField(
        default=dict,
        help_text="Dados completos da requisição POST (além de file_id)"
    )
    class Meta:
        verbose_name = "Arquivo Processado"
        verbose_name_plural = "Arquivos Processados"

    def __str__(self):
        return f"Processamento de {self.file.id} por {self.processed_by.email}"