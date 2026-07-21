import decimal
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from .models import FileUpload
from .utils import convert_decimals_to_json_safe, get_beneficiary_summary

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
        safe_data = convert_decimals_to_json_safe(data)
        
        self.assertEqual(safe_data["valor"], "10.50")
        self.assertEqual(safe_data["lista"][0], "1.00")
        self.assertEqual(safe_data["lista"][1]["sub"], "2.00")
        self.assertIsInstance(safe_data["valor"], str)

    def test_utils_beneficiary_summary_aggregation(self):
        """Testa se o sumário agrupa corretamente valores por CPF"""
        summary = get_beneficiary_summary(self.mock_parsed_data)
        
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


import io
from unittest.mock import patch, MagicMock
import openpyxl
from .confirmed import _gerar_e_upload_planilha_editada


class PlanilhaEditadaS3ExtensaoTest(TestCase):
    """Garante que a planilha editada sempre seja salva no S3 com extensão permitida."""

    def setUp(self):
        self.user = User.objects.create_user(email="test_ext@admin.com", password="password")

    def _criar_workbook_xlsx(self):
        wb = openpyxl.Workbook()
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.read()

    def _criar_upload(self, s3_key, file_name='planilha.xlsx'):
        return FileUpload.objects.create(
            uploaded_by=self.user,
            process_status='PARSED',
            file=f'docs/{file_name}',
            arquivo_s3=f'https://fedcorp-prod.s3.us-east-2.amazonaws.com/{s3_key}'
        )

    @patch('upload.confirmed.boto3.client')
    @patch('upload.confirmed.editar_planilha_original')
    def test_planilha_editada_sempre_salva_com_extensao_valida(self, mock_editar, mock_boto3_client):
        """Se a chave S3 original vier sem extensão, o arquivo editado deve receber uma extensão válida."""
        xlsx_bytes = self._criar_workbook_xlsx()
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3

        def download_side_effect(bucket, key, file_path):
            with open(file_path, 'wb') as f:
                f.write(xlsx_bytes)

        mock_s3.download_file.side_effect = download_side_effect
        mock_editar.return_value = io.BytesIO(xlsx_bytes)

        upload = self._criar_upload('VR - DOCS/importacoes/planilha_sem_extensao', 'planilha_sem_extensao')

        url = _gerar_e_upload_planilha_editada(
            file_upload=upload,
            dados_modificados={'condominios': []},
            data_competencia=None,
            request_user=self.user
        )

        self.assertIsNotNone(url)
        self.assertTrue(
            url.endswith(('.xlsx', '.xlsm', '.txt')),
            f"URL da planilha editada deve terminar com extensão permitida: {url}"
        )

        mock_s3.upload_fileobj.assert_called_once()
        args, kwargs = mock_s3.upload_fileobj.call_args
        s3_key = args[2]
        self.assertTrue(
            s3_key.endswith(('.xlsx', '.xlsm', '.txt')),
            f"Chave S3 da planilha editada deve terminar com extensão permitida: {s3_key}"
        )

        upload.refresh_from_db()
        self.assertEqual(upload.arquivo_s3_editado, url)
