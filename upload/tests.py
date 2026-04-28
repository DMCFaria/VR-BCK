import decimal
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from .models import FileUpload
from .utils import _convert_decimals_to_json_safe, _get_beneficiary_summary

User = get_user_model()

class GeneralUploadIntegrationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="test@admin.com", password="password")
        self.client.force_authenticate(user=self.user)
        
        self.mock_parsed_data = {
            'condominios': [
                {
                    'nome': 'Condo X',
                    'cnpj': '12345678901234',
                    'valor_condo': decimal.Decimal('200.50'),
                    'funcionarios': [
                        {
                            'nome': 'User A',
                            'cpf': '11122233344',
                            'matricula': '123',
                            'departamento': 'CONDOMINIO',
                            'funcao': 'Porteiro',
                            'data_nascimento': '1990-01-01',
                            'valor_bene': decimal.Decimal('200.50'),
                            'movimentacoes': [
                                {'produto': 'VR ALIMENTACAO', 'valor': decimal.Decimal('150.50')},
                                {'produto': 'TRANSPORTE', 'valor': decimal.Decimal('50.00')}
                            ]
                        }
                    ]
                },
                {
                    'nome': 'Condo Y',
                    'cnpj': '98765432109876',
                    'valor_condo': decimal.Decimal('300.00'),
                    'funcionarios': [
                        {
                            'nome': 'User B',
                            'cpf': '55566677788',
                            'matricula': '456',
                            'departamento': 'CONDOMINIO',
                            'funcao': 'Zelador',
                            'data_nascimento': '1985-05-15',
                            'valor_bene': decimal.Decimal('300.00'),
                            'movimentacoes': [
                                {'produto': 'VR ALIMENTACAO', 'valor': decimal.Decimal('300.00')}
                            ]
                        }
                    ]
                }
            ]
        }

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
        
        user_a = next(item for item in summary if item["cpf"] == "11122233344")
        self.assertEqual(user_a["valor_total"], "200.50")
        self.assertEqual(len(summary), 2)

    def test_full_flow_confirmation_failure(self):
        """Testa tentativa de confirmação sem o ID do upload (Erro de Payload)"""
        response = self.client.post('/api/upload/confirm/', {"dados": "vazios"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirmation_view_lock_prevent_double_process(self):
        """Testa se o sistema impede processar o mesmo arquivo duas vezes (Status COMPLETED)"""
        upload = FileUpload.objects.create(
            uploaded_by=self.user,
            process_status='COMPLETED',
            file='docs/test.txt'
        )
        
        payload = {
            "file_upload_id": upload.id,
            "condominios": []
        }
        response = self.client.post('/api/upload/confirm/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("já foi processado", response.data['detail'])

    def test_list_confirmed_uploads_access(self):
        """Testa se a listagem de confirmados está protegida por autenticação"""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/upload/list-confirmed/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)