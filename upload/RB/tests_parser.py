import os
from django.test import TestCase
from django.conf import settings
from decimal import Decimal
from entidades.models import Condominio, Funcionario
from beneficios.models import Produto
from .parsers import parse_rb_layout


class RBParserTestCase(TestCase):
    def setUp(self):
        Condominio.objects.all().delete()
        Funcionario.objects.all().delete()
        Condominio.objects.create(cnpj="12345678901234", nome="Condominio Antigo")
        Funcionario.objects.create(cpf="11122233344", nome="Funcionario Antigo", departamento="RH")

    def write_test_file(self, lines):
        path = os.path.join(settings.BASE_DIR, "test_temp_layout.txt")
        with open(path, 'w', encoding='latin-1') as f:
            for line in lines:
                f.write(line + "\n")
        return path

    def test_arquivo_producao_real(self):
        path = os.path.join(settings.BASE_DIR, '070426001.txt')
        if not os.path.exists(path):
            self.skipTest(f"Arquivo {path} não encontrado na raiz. Pulando teste real.")

        result = parse_rb_layout(path, 1)

        if result['errors']:
            print(f"\n[DEBUG] Erros no arquivo real: {result['errors'][:5]}")

        self.assertEqual(len(result['errors']), 0, "O arquivo de produção real apresentou erros de layout.")
        self.assertGreater(result['summary']['total_movimentacoes'], 0, "Nenhuma movimentação lida no arquivo real.")
        self.assertIn('condominios', result)

    def test_parsing_sucesso_completo(self):
        line0 = list(" " * 200)
        line0[0:5] = "00001"
        line0[5] = "0"
        line0[5:13] = "20260301"
        tipo0 = "".join(line0)

        line1 = list(" " * 200)
        line1[0:5] = "00002"
        line1[5] = "1"
        line1[6:19] = "12345678901234"
        line1[20:60] = "CONDOMINIO TESTE"
        tipo1 = "".join(line1)

        line3 = list(" " * 458)
        line3[0:5] = "00003"
        line3[5] = "3"
        line3[6:19] = "12345678901234"
        line3[19:32] = "MAT123".ljust(13)
        line3[32:72] = "JOAO DA SILVA".ljust(40)
        line3[92:102] = "CONDOMINIO"
        line3[132:139] = "PORTEIRO"
        line3[172:180] = "01011990"
        line3[183:194] = "16975222703"
        tipo3 = "".join(line3)

        line4 = list(" " * 120)
        line4[0:5] = "00004"
        line4[5] = "4"
        line4[6:19] = "12345678901234"
        line4[19:32] = "MAT123".ljust(13)
        line4[44:88] = "VALE REFEICAO - TICKET"
        line4[100:104] = "0001"
        line4[104:112] = "00005000"
        tipo4 = "".join(line4)

        path = self.write_test_file([tipo0, tipo1, tipo3, tipo4])
        result = parse_rb_layout(path, 1)

        self.assertEqual(len(result['errors']), 0, f"Erros encontrados: {result['errors']}")
        self.assertEqual(result['summary']['total_movimentacoes'], 1)
        self.assertEqual(result['summary']['total_condominios'], 1)
        self.assertEqual(result['summary']['total_funcionarios'], 1)
        self.assertEqual(len(result['condominios']), 1)

        condo = result['condominios'][0]
        self.assertEqual(condo['nome'], "CONDOMINIO TESTE")
        self.assertEqual(len(condo['funcionarios']), 1)

        func = condo['funcionarios'][0]
        self.assertEqual(func['nome'], "JOAO DA SILVA")
        self.assertEqual(func['cpf'], "16975222703")
        self.assertEqual(func['departamento'], "CONDOMINIO")
        self.assertEqual(func['funcao'], "PORTEIRO")
        self.assertEqual(len(func['movimentacoes']), 1)
        self.assertIn("VALE REFEICAO", func['movimentacoes'][0]['produto'])

        if os.path.exists(path):
            os.remove(path)

    def test_registro_tipo_4_sem_funcionario(self):
        line1 = list(" " * 200)
        line1[0:5] = "00001"
        line1[5] = "1"
        line1[6:19] = "12345678901234"
        line1[20:60] = "CONDOMINIO TESTE"
        tipo1 = "".join(line1)

        line4 = list(" " * 120)
        line4[0:5] = "00002"
        line4[5] = "4"
        line4[6:19] = "12345678901234"
        line4[19:32] = "MAT999".ljust(13)
        line4[44:88] = "VALE REFEICAO"
        line4[100:104] = "0001"
        line4[104:112] = "00001000"
        tipo4 = "".join(line4)

        path = self.write_test_file([tipo1, tipo4])
        result = parse_rb_layout(path, 1)

        self.assertTrue(any("não encontrada" in err for err in result['errors']))
        os.remove(path)

    def test_validacao_cpf_invalido(self):
        line1 = list(" " * 200)
        line1[0:5] = "00001"
        line1[5] = "1"
        line1[6:19] = "12345678901234"
        line1[20:60] = "CONDOMINIO TESTE"
        tipo1 = "".join(line1)

        line3 = list(" " * 458)
        line3[0:5] = "00002"
        line3[5] = "3"
        line3[6:19] = "12345678901234"
        line3[19:32] = "MAT123".ljust(13)
        line3[32:72] = "JOAO DA SILVA".ljust(40)
        line3[183:194] = "00000000000"
        tipo3 = "".join(line3)

        path = self.write_test_file([tipo1, tipo3])
        result = parse_rb_layout(path, 1)

        self.assertTrue(any("CPF inválido" in err for err in result['errors']))
        os.remove(path)

    def test_parsing_varios_funcionarios(self):
        line0 = list(" " * 200)
        line0[0:5] = "00001"
        line0[5] = "0"
        line0[5:13] = "20260301"
        tipo0 = "".join(line0)

        line1 = list(" " * 200)
        line1[0:5] = "00002"
        line1[5] = "1"
        line1[6:19] = "12345678901234"
        line1[20:60] = "CONDO UM"
        tipo1 = "".join(line1)

        line3a = list(" " * 458)
        line3a[0:5] = "00003"
        line3a[5] = "3"
        line3a[6:19] = "12345678901234"
        line3a[19:32] = "MAT001".ljust(13)
        line3a[32:72] = "FUNCIONARIO A".ljust(40)
        line3a[92:102] = "CONDOMINIO"
        line3a[132:139] = "PORTEIRO"
        line3a[172:180] = "01011990"
        line3a[183:194] = "11122233344"
        tipo3a = "".join(line3a)

        line4a = list(" " * 120)
        line4a[0:5] = "00004"
        line4a[5] = "4"
        line4a[6:19] = "12345678901234"
        line4a[19:32] = "MAT001".ljust(13)
        line4a[44:88] = "VR ALIMENTACAO"
        line4a[100:104] = "0001"
        line4a[104:112] = "00001000"
        tipo4a = "".join(line4a)

        line3b = list(" " * 458)
        line3b[0:5] = "00005"
        line3b[5] = "3"
        line3b[6:19] = "12345678901234"
        line3b[19:32] = "MAT002".ljust(13)
        line3b[32:72] = "FUNCIONARIO B".ljust(40)
        line3b[92:102] = "CONDOMINIO"
        line3b[132:139] = "ZELADOR"
        line3b[172:180] = "02021985"
        line3b[183:194] = "55566677788"
        tipo3b = "".join(line3b)

        line4b = list(" " * 120)
        line4b[0:5] = "00006"
        line4b[5] = "4"
        line4b[6:19] = "12345678901234"
        line4b[19:32] = "MAT002".ljust(13)
        line4b[44:88] = "VR REFEICAO"
        line4b[100:104] = "0001"
        line4b[104:112] = "00001500"
        tipo4b = "".join(line4b)

        path = self.write_test_file([tipo0, tipo1, tipo3a, tipo4a, tipo3b, tipo4b])
        result = parse_rb_layout(path, 1)

        self.assertEqual(len(result['errors']), 0)
        self.assertEqual(result['summary']['total_condominios'], 1)
        self.assertEqual(result['summary']['total_funcionarios'], 2)
        self.assertEqual(result['summary']['total_movimentacoes'], 2)
        self.assertEqual(len(result['condominios']), 1)
        self.assertEqual(len(result['condominios'][0]['funcionarios']), 2)

        if os.path.exists(path):
            os.remove(path)