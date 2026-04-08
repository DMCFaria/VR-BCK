import os
import tempfile
from django.test import TestCase
from decimal import Decimal
from entidades.models import Condominio, Funcionario
from beneficios.models import Produto
from .parsers import parse_rb_layout

class RBParserTestCase(TestCase):
    def setUp(self):
        # Criamos dados pré-existentes para testar a lógica de "Novos Registros"
        Condominio.objects.create(cnpj="1234567890123", nome="Condominio Antigo")
        Funcionario.objects.create(cpf="11122233344", nome="Funcionario Antigo", departamento="RH")
        Produto.objects.create(codigo_produto="00001", nome="VT")

    def create_mock_file(self, lines):
        """Auxiliar para criar um arquivo temporário com o layout fornecido"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='latin-1')
        for line in lines:
            temp_file.write(line + '\n')
        temp_file.close()
        return temp_file.name

    def test_parsing_sucesso_completo(self):
        """Teste de 'Caminho Feliz' com fluxo completo (Tipos 1, 2, 3 e 4)"""
        lines = [
            "00001 20240501" + " " * 100, # Header com data
            "00002 19876543210987  CONDOMINIO TESTE S/A", # Tipo 1
            "00003 2 04000000 RUA DAS FLORES         123       BAIRRO CENTRO        SAO PAULO           SP ", # Tipo 2
            "00004 3            MAT123       JOAO DA SILVA                                   01011990   12345678901", # Tipo 3
            "00005 4            MAT123                 00002PRODUTO TESTE                      002200005000", # Tipo 4 (22 dias, R$ 50,00)
        ]
        path = self.create_mock_file(lines)
        
        try:
            result = parse_rb_layout(path, 1)
            
            self.assertNotIn('error', result)
            self.assertEqual(len(result['movimentacoes_detalhada']), 1)
            
            # Verificação de valores calculados (22 * 50.00 = 1100.00)
            linha = result['movimentacoes_detalhada'][0]
            self.assertEqual(linha['valor_recarga_bene'], Decimal('1100.00'))
            self.assertEqual(linha['cpf_func'], '12345678901')
            
            # Verificação de novos registros
            self.assertEqual(result['novos_registros']['Total de funcionários novos'], 1)
        finally:
            os.remove(path)

    def test_falha_valor_nao_numerico_no_beneficio(self):
        """Tenta quebrar o format_valor com caracteres inválidos onde deveria ser dinheiro"""
        lines = [
            "00001 20240501",
            "00002 19876543210987  CONDO TESTE",
            "00004 3            MAT123       JOAO SILVA                                      01011990   12345678901",
            "00005 4            MAT123                 00002PRODUTO                            0022ABCDEFGH", # Valor corrompido
        ]
        path = self.create_mock_file(lines)
        result = parse_rb_layout(path, 1)
        
        # O format_valor deve retornar Decimal(0) e não estourar Exception
        self.assertEqual(result['movimentacoes_detalhada'][0]['valor_recarga_bene'], Decimal('0.00'))
        os.remove(path)

    def test_data_nascimento_invalida(self):
        """Tenta passar uma data impossível (32 de dezembro)"""
        lines = [
            "00001 20240501",
            "00004 3            MAT123       JOAO SILVA                                      32121990   12345678901",
        ]
        path = self.create_mock_file(lines)
        result = parse_rb_layout(path, 1)
        
        # O format_date deve retornar None e não travar o loop
        self.assertIsNone(result['novos_registros']['funcionarios'][0]['data_nascimento'])
        os.remove(path)

    def test_arquivo_vazio_ou_so_espacos(self):
        """Garante que o parser lida com arquivos fantasmas"""
        path = self.create_mock_file([" ", "          ", ""])
        result = parse_rb_layout(path, 1)
        
        self.assertEqual(result['summary']['total_movimentacoes'], 0)
        os.remove(path)

    def test_registro_tipo_4_sem_tipo_3_anterior(self):
        """Cenário de erro: Benefício órfão (sem funcionário carregado no cache)"""
        lines = [
            "00001 20240501",
            "00002 19876543210987  CONDO TESTE",
            "00005 4            MAT999                 00002PRODUTO                            002200005000",
        ]
        path = self.create_mock_file(lines)
        result = parse_rb_layout(path, 1)
        
        # Não deve criar movimentação pois não achou a matrícula no cache
        self.assertEqual(len(result['movimentacoes_detalhada']), 0)
        os.remove(path)

    def test_mix_registros_existentes_e_novos(self):
        """Valida se o parser identifica corretamente quem já está no banco"""
        lines = [
            "00001 20240501",
            "00002 11234567890123  NOVO CONDO", # Novo CNPJ
            "00004 3            MAT999       NOVO FUNC                                       01011990   99988877766", # Novo CPF
            "00004 3            MAT111       ANTIGO                                          01011990   11122233344", # CPF JÁ EXISTE NO SETUP
        ]
        path = self.create_mock_file(lines)
        result = parse_rb_layout(path, 1)
        
        # Deve haver apenas 1 funcionário novo na lista de novos_registros
        self.assertEqual(len(result['novos_registros']['funcionarios']), 1)
        self.assertEqual(result['novos_registros']['funcionarios'][0]['cpf'], '99988877766')
        os.remove(path)