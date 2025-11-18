from django.db import models
# Certifique-se de que a importação do seu modelo de usuário está correta
# Se o CustomUser estiver em outro app, use from <seu_app>.models import CustomUser
from users.models import CustomUser


class FileUpload(models.Model):
    
    STATUS_CHOICES = [
        ("PENDING", "Pendente"),
        ("VALIDATED", "Validado"),  # Correção ortográfica de VALITED para VALIDATED
        ("FAILED", "Falhou")
    ]
    
    TYPE_CHOICES = [
        ("RB", "Modelo da RB"),
        # Adicione outros tipos de layout aqui se necessário
    ]
    
    # Armazena o arquivo
    file = models.FileField(upload_to='docs/')
    
    # Usuário que enviou (Relacionamento Foreign Key)
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    
    # Data de upload
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Status atual do processamento
    process_status = models.CharField(
        choices=STATUS_CHOICES, 
        default="PENDING", 
        max_length=10
    )
    
    # Tipo de layout (Modelo da RB, por exemplo)
    file_type = models.CharField(
        choices=TYPE_CHOICES, 
        max_length=10, # Alterado para 10, que é suficiente para "RB"
        default="RB"
    )

    # Campo para armazenar o resumo (Número de condomínios, Valor total) antes da confirmação
    summary_data = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.file.name} - Status: {self.process_status}"
    
    
class ProcessedFile(models.Model):
    
    
    file = models.ForeignKey(FileUpload, on_delete=models.CASCADE)
    processed_at = models.DateTimeField(auto_now_add=True)
    processed_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    

    
    def __str__(self):
        return f"Processado: {self.file.file.name}"