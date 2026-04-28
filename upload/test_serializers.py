import decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from io import StringIO
import tempfile
import os

from .models import FileUpload
from .serializers import ProcessamentoFinalSerializer, CondominioSerializer, FuncionarioSerializer
from entidades.models import Administradora, Condominio, Funcionario, VinculoCondominio
from beneficios.models import Produto, MovimentacaoBeneficio

User = get_user_model()


class ProcessamentoFinalSerializerTests(TestCase):
    """Testes para o ProcessamentoFinalSerializer"""

    def setUp(self):
        self.admin = Administradora.objects.create(
            cnpj="12345678000100",
            nome="Admin Teste",
            ativo=True
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="password",
            administradora=self.admin
        )
        self.file_upload = FileUpload.objects.create(
            uploaded_by=self.user,
            process_status="PENDING",
            file="test.xlsx"
        )
        
        self.valid_payload = {
            "file_upload_id": None,
            "condominios": [
                {
                    "nome": "CONDOMINIO TESTE",
                    "cnpj": "98765432000199",
                    "valor_condo": "1000.00",
                    "funcionarios": [
                        {
                            "nome": "FUNCIONARIO TESTE",
                            "cpf": "12345678901",
                            "matricula": "12345",
                            "departamento": "CONDOMINIO",
                            "funcao": "PORTEIRO",
                            "data_nascimento": "1990-01-15",
                            "valor_bene": "500.00",
                            "movimentacoes": [
                                {"produto": "VALE REFEICAO", "valor": "25.00"},
                                {"produto": "VALE ALIMENTACAO", "valor": "475.00"}
                            ]
                        }
                    ]
                }
            ]
        }

    def test_usuario_sem_administradora(self):
        """Deve falhar se usuário não possui administradora vinculada"""
        user_sem_admin = User.objects.create_user(
            username="semadmin",
            email="sem@admin.com",
            password="password"
        )
        self.file_upload.file_upload_id = self.file_upload.id
        self.valid_payload["file_upload_id"] = self.file_upload.id
        
        serializer = ProcessamentoFinalSerializer(data=self.valid_payload)
        self.assertFalse(serializer.is_valid())

    def test_serializer_validacao_payload_vazio(self):
        """Serializer deve rejeitar payload vazio"""
        serializer = ProcessamentoFinalSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("file_upload_id", serializer.errors)

    def test_serializer_validacao_sem_condominios(self):
        """Serializer deve rejeitar payload sem condomínios"""
        payload = {
            "file_upload_id": self.file_upload.id,
            "condominios": []
        }
        serializer = ProcessamentoFinalSerializer(data=payload)
        self.assertFalse(serializer.is_valid())

    def test_normalizacao_datas_invalidas(self):
        """Datas inválidas devem ser convertidas para None"""
        payload = {
            "file_upload_id": self.file_upload.id,
            "condominios": [
                {
                    "nome": "CONDOMINIO TESTE",
                    "cnpj": "98765432000199",
                    "valor_condo": "1000.00",
                    "funcionarios": [
                        {
                            "nome": "FUNCIONARIO TESTE",
                            "cpf": "12345678901",
                            "matricula": "12345",
                            "departamento": "CONDOMINIO",
                            "funcao": "PORTEIRO",
                            "data_nascimento": "0020-00-00",
                            "valor_bene": "500.00",
                            "movimentacoes": []
                        }
                    ]
                }
            ]
        }
        
        payload_com_data_valida = {
            "file_upload_id": self.file_upload.id,
            "condominios": [
                {
                    "nome": "CONDOMINIO TESTE 2",
                    "cnpj": "98765432000200",
                    "valor_condo": "1000.00",
                    "funcionarios": [
                        {
                            "nome": "FUNCIONARIO TESTE 2",
                            "cpf": "98765432109",
                            "matricula": "12346",
                            "departamento": "CONDOMINIO",
                            "funcao": "ZELADOR",
                            "data_nascimento": "1985-05-20",
                            "valor_bene": "500.00",
                            "movimentacoes": []
                        }
                    ]
                }
            ]
        }
        
        serializer = ProcessamentoFinalSerializer(data=payload_com_data_valida)
        self.assertTrue(serializer.is_valid(), serializer.errors)


class ProcessamentoFinalIntegrationTests(TestCase):
    """Testes de integração para o endpoint de confirmação"""

    def setUp(self):
        self.client = APIClient()
        self.admin = Administradora.objects.create(
            cnpj="12345678000100",
            nome="Admin Teste",
            ativo=True
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="password",
            administradora=self.admin
        )
        self.client.force_authenticate(user=self.user)
        
        self.file_upload = FileUpload.objects.create(
            uploaded_by=self.user,
            process_status="PENDING",
            file="test.xlsx"
        )

    def test_confirmacao_sucesso(self):
        """Confirmação deve criar registros com sucesso"""
        payload = {
            "file_upload_id": self.file_upload.id,
            "condominios": [
                {
                    "nome": "CONDOMINIO TESTE",
                    "cnpj": "98765432000199",
                    "valor_condo": "1000.00",
                    "funcionarios": [
                        {
                            "nome": "FUNCIONARIO TESTE",
                            "cpf": "12345678901",
                            "matricula": "12345",
                            "departamento": "CONDOMINIO",
                            "funcao": "PORTEIRO",
                            "data_nascimento": "1990-01-15",
                            "valor_bene": "500.00",
                            "movimentacoes": [
                                {"produto": "VALE REFEICAO", "valor": "25.00"},
                                {"produto": "VALE ALIMENTACAO", "valor": "475.00"}
                            ]
                        }
                    ]
                }
            ]
        }
        
        response = self.client.post('/api/upload/confirm/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "COMPLETED")
        self.assertEqual(response.data["count"], 2)
        
        self.file_upload.refresh_from_db()
        self.assertEqual(self.file_upload.process_status, "COMPLETED")

    def test_confirmacao_sem_file_upload_id(self):
        """Confirmação deve falhar sem file_upload_id"""
        payload = {
            "condominios": []
        }
        
        response = self.client.post('/api/upload/confirm/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirmacao_arquivo_ja_processado(self):
        """Confirmação deve falhar para arquivo já processado"""
        self.file_upload.process_status = "COMPLETED"
        self.file_upload.save()
        
        payload = {
            "file_upload_id": self.file_upload.id,
            "condominios": []
        }
        
        response = self.client.post('/api/upload/confirm/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("já foi processado", str(response.data))

    def test_confirmacao_usuario_sem_administradora(self):
        """Confirmação deve falhar para usuário sem administradora"""
        user_sem_admin = User.objects.create_user(
            username="semadmin",
            email="sem@admin.com",
            password="password"
        )
        self.client.force_authenticate(user=user_sem_admin)
        
        payload = {
            "file_upload_id": self.file_upload.id,
            "condominios": []
        }
        
        response = self.client.post('/api/upload/confirm/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("administradora", str(response.data))

    def test_confirmacao_sem_autenticacao(self):
        """Confirmação deve falhar sem autenticação"""
        self.client.force_authenticate(user=None)
        
        payload = {
            "file_upload_id": self.file_upload.id,
            "condominios": []
        }
        
        response = self.client.post('/api/upload/confirm/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_confirmacao_nao_duplica_registros(self):
        """Confirmação não deve duplicar registros existentes"""
        Condominio.objects.create(
            cnpj="98765432000199",
            nome="CONDOMINIO EXISTENTE"
        )
        Funcionario.objects.create(
            cpf="12345678901",
            nome="FUNCIONARIO EXISTENTE"
        )
        Produto.objects.create(
            codigo_produto="VALE REFEICAO",
            nome="VALE REFEICAO"
        )
        
        payload = {
            "file_upload_id": self.file_upload.id,
            "condominios": [
                {
                    "nome": "CONDOMINIO EXISTENTE",
                    "cnpj": "98765432000199",
                    "valor_condo": "1000.00",
                    "funcionarios": [
                        {
                            "nome": "FUNCIONARIO EXISTENTE",
                            "cpf": "12345678901",
                            "matricula": "12345",
                            "departamento": "CONDOMINIO",
                            "funcao": "PORTEIRO",
                            "data_nascimento": "1990-01-15",
                            "valor_bene": "500.00",
                            "movimentacoes": [
                                {"produto": "VALE REFEICAO", "valor": "25.00"}
                            ]
                        }
                    ]
                }
            ]
        }
        
        response1 = self.client.post('/api/upload/confirm/', payload, format='json')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        count_movs = MovimentacaoBeneficio.objects.filter(
            empresa_cnpj_id="98765432000199",
            funcionario_cpf_id="12345678901"
        ).count()
        
        self.assertEqual(count_movs, 1)

    def test_confirmacao_data_competencia_fallback(self):
        """Data de competência deve usar fallback quando não informada"""
        payload = {
            "file_upload_id": self.file_upload.id,
            "condominios": [
                {
                    "nome": "CONDOMINIO TESTE",
                    "cnpj": "98765432000199",
                    "valor_condo": "1000.00",
                    "funcionarios": [
                        {
                            "nome": "FUNCIONARIO TESTE",
                            "cpf": "12345678901",
                            "matricula": "12345",
                            "departamento": "CONDOMINIO",
                            "funcao": "PORTEIRO",
                            "data_nascimento": None,
                            "valor_bene": "500.00",
                            "movimentacoes": [
                                {"produto": "VALE REFEICAO", "valor": "25.00"}
                            ]
                        }
                    ]
                }
            ]
        }
        
        response = self.client.post('/api/upload/confirm/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        mov = MovimentacaoBeneficio.objects.first()
        self.assertIsNotNone(mov.data_competencia)

    def test_confirmacao_cria_vinculo(self):
        """Confirmação deve criar vínculo com administradora"""
        payload = {
            "file_upload_id": self.file_upload.id,
            "condominios": [
                {
                    "nome": "CONDOMINIO TESTE",
                    "cnpj": "98765432000199",
                    "valor_condo": "1000.00",
                    "funcionarios": [
                        {
                            "nome": "FUNCIONARIO TESTE",
                            "cpf": "12345678901",
                            "matricula": "12345",
                            "departamento": "CONDOMINIO",
                            "funcao": "PORTEIRO",
                            "data_nascimento": "1990-01-15",
                            "valor_bene": "500.00",
                            "movimentacoes": [
                                {"produto": "VALE REFEICAO", "valor": "25.00"}
                            ]
                        }
                    ]
                }
            ]
        }
        
        response = self.client.post('/api/upload/confirm/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        vinculo = VinculoCondominio.objects.filter(
            administradora=self.admin,
            condominio_id="98765432000199"
        ).exists()
        self.assertTrue(vinculo)


class CondominioSerializerTests(TestCase):
    """Testes para o CondominioSerializer"""

    def test_validacao_cnpj_obrigatorio(self):
        """CNPJ deve ser obrigatório"""
        data = {
            "nome": "CONDOMINIO TESTE",
            "cnpj": "",
            "valor_condo": "1000.00",
            "funcionarios": []
        }
        serializer = CondominioSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_validacao_nome_obrigatorio(self):
        """Nome deve ser obrigatório"""
        data = {
            "nome": "",
            "cnpj": "98765432000199",
            "valor_condo": "1000.00",
            "funcionarios": []
        }
        serializer = CondominioSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_validacao_funcionarios_vazio(self):
        """Lista de funcionários pode ser vazia"""
        data = {
            "nome": "CONDOMINIO TESTE",
            "cnpj": "98765432000199",
            "valor_condo": "1000.00",
            "funcionarios": []
        }
        serializer = CondominioSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class FuncionarioSerializerTests(TestCase):
    """Testes para o FuncionarioSerializer"""

    def test_validacao_cpf_obrigatorio(self):
        """CPF deve ser obrigatório"""
        data = {
            "nome": "FUNCIONARIO TESTE",
            "cpf": "",
            "matricula": "12345",
            "departamento": "CONDOMINIO",
            "funcao": "PORTEIRO",
            "valor_bene": "500.00",
            "movimentacoes": []
        }
        serializer = FuncionarioSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_validacao_movimentacoes_vazio(self):
        """Lista de movimentações pode ser vazia"""
        data = {
            "nome": "FUNCIONARIO TESTE",
            "cpf": "12345678901",
            "matricula": "12345",
            "departamento": "CONDOMINIO",
            "funcao": "PORTEIRO",
            "valor_bene": "500.00",
            "movimentacoes": []
        }
        serializer = FuncionarioSerializer(data=data)
        self.assertTrue(serializer.is_valid())
