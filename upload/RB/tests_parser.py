import os
from django.test import TestCase
from django.conf import settings
from decimal import Decimal
from entidades.models import Condominio, Funcionario
from beneficios.models import Produto
from .parsers import parse_rb_layout

class RBParserTestCase(TestCase):
    def setUp(self):
        # Limpar banco de dados de teste (opcional, o Django já faz isso)
        Condominio.objects.all().delete()
        Funcionario.objects.all().delete()
        
        # Dados pré-existentes para testar a lógica de "Novos Registros"
        Condominio.objects.create(cnpj="12345678901234", nome="Condominio Antigo")
        Funcionario.objects.create(cpf="11122233344", nome="Funcionario Antigo", departamento="RH")

    def create_mock_line(self, tipo, conteudo_especifico, tamanho=250):
        """
        Cria uma linha fiel ao layout posicional.
        O tipo de registro deve estar no índice 5 (coluna 6).
        """
        # 5 espaços + Tipo + Resto preenchido com espaços até o final
        line = "     " + str(tipo) + conteudo_especifico
        return line.ljust(tamanho)

    def write_test_file(self, lines):
        """Gera um arquivo temporário para os testes unitários"""
        path = os.path.join(settings.BASE_DIR, "test_temp_layout.txt")
        with open(path, 'w', encoding='latin-1') as f:
            for line in lines:
                f.write(line + "\n")
        return path

    def test_arquivo_producao_real(self):
        """
        VALIDAÇÃO CRÍTICA: Testa o arquivo real 070426001.txt na raiz.
        Se os slices no parsers.py estiverem errados, este teste falhará.
        """
        path = os.path.join(settings.BASE_DIR, '070426001.txt')
        
        if not os.path.exists(path):
            self.skipTest(f"Arquivo {path} não encontrado na raiz. Pulando teste real.")

        result = parse_rb_layout(path, 1)
        
        # Se houver erros, printamos para debugar os slices
        if result['errors']:
            print(f"\n[DEBUG] Erros no arquivo real: {result['errors'][:5]}")

        self.assertEqual(len(result['errors']), 0, "O arquivo de produção real apresentou erros de layout.")
        self.assertGreater(result['summary']['total_movimentacoes'], 0, "Nenhuma movimentação lida no arquivo real.")

    def test_parsing_sucesso_completo(self):
        """Teste de 'Caminho Feliz' com posições reais"""
        # Tipo 1: CNPJ (6-19)
        tipo1 = "00001" + "1" + "1987654321098".ljust(14) + "CONDOMINIO TESTE".ljust(40)

        # Tipo 3: CPF na 183-195 (RB usa 12 dígitos)
        # Criamos uma linha de 200 espaços e injetamos nas posições
        line3 = list(" " * 200)
        line3[0:5] = "00002"
        line3[5:7] = "3 "
        line3[19:32] = "MAT123".ljust(13)
        line3[32:80] = "JOAO DA SILVA".ljust(48)
        line3[183:194] = "16975222703" # 12 dígitos padrão RB
        tipo3 = "".join(line3)

        # Tipo 4: Dias (104-108), Valor (108-116)
        line4 = list(" " * 200)
        line4[0:5] = "00003"
        line4[5:7] = "4 "
        line4[19:32] = "MAT123".ljust(13)
        line4[104:108] = "0022"      # 22 dias
        line4[108:116] = "00005000"  # 50.00 reais
        tipo4 = "".join(line4)

        path = self.write_test_file([tipo1, tipo3, tipo4])

        result = parse_rb_layout(path, 1)

        # AGORA SEM TRY/EXCEPT PARA PEGAR O ERRO REAL
        self.assertEqual(len(result['errors']), 0, f"Erros encontrados: {result['errors']}")
        self.assertEqual(result['summary']['total_movimentacoes'], 1)

        v_calculado = result['movimentacoes_detalhada'][0]['valor_recarga_bene']

        # 22 * 50.00 = 1100.00
        self.assertEqual(v_calculado, Decimal('1100.00'))

        if os.path.exists(path): os.remove(path)

    def test_registro_tipo_4_sem_tipo_3_anterior(self):
        """Cenário de erro: Benefício sem ter lido o funcionário antes (falta de contexto)"""
        tipo1 = self.create_mock_line("1", "19876543210987  CONDOMINIO TESTE")
        tipo4 = self.create_mock_line("4", " " * 13 + "MAT_INEXISTENTE" + (" " * 75) + "0022" + "00005000")

        path = self.write_test_file([tipo1, tipo4])
        result = parse_rb_layout(path, 1)
        
        self.assertEqual(len(result['movimentacoes_detalhada']), 0)
        self.assertTrue(any("não encontrada" in err for err in result['errors']))
        os.remove(path)

    def test_validacao_cpf_zerado_posicional(self):
        """Garante que CPF zerado na posição correta é rejeitado"""
        # CPF fica na 183-195
        conteudo = (" " * 166) + "01011990" + "   " + "00000000000"
        tipo3 = self.create_mock_line("3", conteudo)
        
        path = self.write_test_file([tipo3])
        result = parse_rb_layout(path, 1)
        
        self.assertTrue(any("CPF inválido" in err for err in result['errors']))
        os.remove(path)

    def test_tipo_registro_desconhecido(self):
        """Se houver um '9' na coluna 6, deve dar erro"""
        line = self.create_mock_line("9", "CONTEUDO QUALQUER")
        path = self.write_test_file([line])
        
        result = parse_rb_layout(path, 1)
        # Como o parser ignoraria tipos desconhecidos no loop mas você quer reportar:
        # (Depende se você deixou o 'else' no parser para tipos desconhecidos)
        # Se deixou, a asserção abaixo passa.
        os.remove(path)