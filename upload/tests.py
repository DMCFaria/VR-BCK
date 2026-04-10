import decimal
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from .models import FileUpload, ProcessedFile
from .utils import _convert_decimals_to_json_safe, _get_beneficiary_summary

User = get_user_model()

class GeneralUploadIntegrationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="test@admin.com", password="password")
        self.client.force_authenticate(user=self.user)
        
        # Mock de dados para o utilitário de sumário
        self.mock_parsed_data = {
            'movimentacoes_detalhada': [
                {
                    'cpf_func': '111', 'nome_func': 'User A', 
                    'valor_recarga_bene': decimal.Decimal('150.50'), 'departamento': 'Condo X'
                },
                {
                    'cpf_func': '111', 'nome_func': 'User A', 
                    'valor_recarga_bene': decimal.Decimal('50.00'), 'departamento': 'Condo X'
                },
                {
                    'cpf_func': '222', 'nome_func': 'User B', 
                    'valor_recarga_bene': decimal.Decimal('300.00'), 'departamento': 'Condo Y'
                }
            ]
        }

    # --- TESTES DE FUNÇÕES AUXILIARES (UTILS) ---

    def test_utils_decimal_conversion(self):
        """Testa se a conversão de Decimal para String para JSON funciona em estruturas profundas"""
        data = {
            "valor": decimal.Decimal("10.50"),
            "lista": [decimal.Decimal("1.00"), {"sub": decimal.Decimal("2.00")}]
        }
        safe_data = _convert_decimals_to_json_safe(data)
        
        self.assertEqual(safe_data["valor"], "10.50")
        self.assertEqual(safe_data["lista"][0], "1.00")
        self.assertEqual(safe_data["lista"][1]["sub"], "2.00")
        self.assertIsInstance(safe_data["valor"], str)

    def test_utils_beneficiary_summary_aggregation(self):
        """Testa se o sumário agrupa corretamente valores por CPF"""
        summary = _get_beneficiary_summary(self.mock_parsed_data)
        
        # User A (111) deve ter 200.50 (150.50 + 50.00)
        user_a = next(item for item in summary if item["cpf"] == "111")
        self.assertEqual(user_a["valor_total"], "200.50")
        self.assertEqual(len(summary), 2) # Apenas 2 funcionários únicos

    # --- TESTES DAS VIEWS (UPLOAD & CONFIRM) ---

    #def test_upload_view_invalid_extension(self):
    #    """Tenta fazer upload de um arquivo .pdf (não suportado)"""
    #    file = SimpleUploadedFile("documento.pdf", b"conteudo_fake", content_type="application/pdf")
    #    response = self.client.post('/api/upload/', {'file': file}, format='multipart')
    #    
    #    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    #    self.assertIn("não permitida", response.data['detail'])

    def test_full_flow_confirmation_failure(self):
        """Testa tentativa de confirmação sem o ID do upload (Erro de Payload)"""
        response = self.client.post('/api/upload/confirm/', {"dados": "vazios"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirmation_view_lock_prevent_double_process(self):
        """Testa se o sistema impede processar o mesmo arquivo duas vezes (Status COMPLETED)"""
        # 1. Cria um upload já finalizado no banco
        upload = FileUpload.objects.create(
            uploaded_by=self.user,
            process_status='COMPLETED',
            file='docs/test.txt'
        )
        
        # 2. Tenta confirmar novamente
        payload = {
            "file_upload_id": upload.id,
            "movimentacoes_detalhada": []
        }
        response = self.client.post('/api/upload/confirm/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("já foi processado", response.data['detail'])

    # --- TESTES DE LISTAGEM (CONFIRMED) ---

    def test_list_confirmed_uploads_access(self):
        """Testa se a listagem de confirmados está protegida por autenticação"""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/upload/list-confirmed/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)