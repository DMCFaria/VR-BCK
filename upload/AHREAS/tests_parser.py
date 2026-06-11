import os
from django.test import TestCase
from django.conf import settings
from decimal import Decimal
from ..layout_detector import detect_txt_layout
from .parsers import (
    parse_ahreas_layout, SEQUENCIAL_FIM,
)


LARGURA_LINHA = 350


def make_line():
    return [' '] * LARGURA_LINHA


def finalize(line_list, sequencial):
    seq = str(sequencial).zfill(9)
    for i, c in enumerate(seq):
        line_list[SEQUENCIAL_FIM.start + i] = c
    return ''.join(line_list)


def set_slice(lst, start, end, value):
    size = end - start
    if len(value) != size:
        value = value.ljust(size)
    lst[start:end] = list(value[:size])


class LayoutDetectorTest(TestCase):
    def test_detect_rb(self):
        content = "00000020260301\n00001103468044000139CONDOMINIO\n"
        path = os.path.join(settings.BASE_DIR, "test_detect_rb.txt")
        with open(path, 'w', encoding='latin-1') as f:
            f.write(content)
        self.assertEqual(detect_txt_layout(path), 'RB')
        os.remove(path)

    def test_detect_ahreas(self):
        content = "0001100662323000140M  BENEDETTI\n10006623230001400337\n"
        path = os.path.join(settings.BASE_DIR, "test_detect_ahreas.txt")
        with open(path, 'w', encoding='latin-1') as f:
            f.write(content)
        self.assertEqual(detect_txt_layout(path), 'AHREAS')
        os.remove(path)


class AHREASParserTest(TestCase):
    def write_test_file(self, lines):
        path = os.path.join(settings.BASE_DIR, "test_temp_ahreas.txt")
        with open(path, 'w', encoding='latin-1') as f:
            for line in lines:
                f.write(line + "\n")
        return path

    def test_arquivo_producao_real(self):
        path = os.path.join(settings.BASE_DIR, 'upload/AHREAS/mbenedetti.txt')
        if not os.path.exists(path):
            self.skipTest(f"Arquivo {path} não encontrado. Pulando teste real.")

        result = parse_ahreas_layout(path, 1)

        if result['errors']:
            print(f"\n[DEBUG] Erros no arquivo real: {result['errors'][:5]}")

        self.assertEqual(len(result['errors']), 0)
        self.assertGreater(result['summary']['total_movimentacoes'], 0)
        self.assertEqual(result['summary']['total_condominios'], 1)
        self.assertEqual(result['summary']['total_funcionarios'], 5)
        self.assertEqual(result['summary']['total_movimentacoes'], 5)
        self.assertEqual(result['summary']['data_competencia_arquivo'], "2026-07-01")
        self.assertIn('condominios', result)

        condo = result['condominios'][0]
        self.assertEqual(condo['nome'], "CONJUNTO RESIDENCIAL TRIUMPH")
        self.assertEqual(condo['cnpj'], "12329457000123")
        self.assertEqual(len(condo['funcionarios']), 5)

    def test_parsing_completo(self):
        h = make_line()
        h[0] = '0'
        set_slice(h, 1, 5, '0011')
        set_slice(h, 5, 19, '00662323000140')
        h[19] = 'M'
        set_slice(h, 22, 60, 'BENEDETTI ASSESSORIA CONDOMINIAL LTDA')
        header = finalize(h, 1)

        c10 = make_line()
        c10[0] = '1'
        c10[1] = '0'
        set_slice(c10, 2, 6, '0066')
        set_slice(c10, 6, 20, '23230001400337')
        set_slice(c10, 46, 86, 'CONJUNTO RESIDENCIAL TRIUMPH')
        set_slice(c10, 126, 130, 'RUA ')
        set_slice(c10, 146, 186, 'TAPAJOS')
        set_slice(c10, 186, 192, '000061')
        set_slice(c10, 212, 242, 'TUPI')
        set_slice(c10, 242, 272, 'PRAIA GRANDE')
        set_slice(c10, 272, 274, 'SP')
        set_slice(c10, 274, 282, '11703340')
        set_slice(c10, 282, 288, 'ZELADOR')
        condo10 = finalize(c10, 2)

        c11 = make_line()
        c11[0] = '1'
        c11[1] = '1'
        set_slice(c11, 2, 6, '0066')
        set_slice(c11, 6, 20, '23230001400337')
        set_slice(c11, 46, 60, '12329457000123')
        set_slice(c11, 60, 80, 'CONJUNTO RESIDENCIAL TRI')
        condo11 = finalize(c11, 3)

        f = make_line()
        f[0] = '3'
        f[1] = '0'
        set_slice(f, 2, 6, '0066')
        set_slice(f, 6, 20, '23230001402635')
        set_slice(f, 16, 27, '26353372841')
        set_slice(f, 27, 31, '0337')
        set_slice(f, 79, 119, 'RICARDO PEREIRA DA SILVA')
        set_slice(f, 143, 151, '07111977')
        f[151] = 'M'
        func = finalize(f, 4)

        comp = make_line()
        comp[0] = '5'
        set_slice(comp, 1, 5, '0006')
        set_slice(comp, 5, 19, '62323000140VBA')
        set_slice(comp, 16, 19, 'VBA')
        set_slice(comp, 19, 27, '01072026')
        competencia = finalize(comp, 9)

        b = make_line()
        b[0] = '6'
        b[1] = '0'
        set_slice(b, 2, 6, '0066')
        set_slice(b, 6, 16, '2323000140')
        set_slice(b, 16, 19, 'VBA')
        set_slice(b, 19, 30, '26353372841')
        set_slice(b, 70, 81, '00000095385')
        beneficio = finalize(b, 10)

        path = self.write_test_file([
            header, condo10, condo11, func, competencia, beneficio
        ])
        result = parse_ahreas_layout(path, 1)

        self.assertEqual(len(result['errors']), 0, f"Erros: {result['errors']}")
        self.assertEqual(result['summary']['total_condominios'], 1)
        self.assertEqual(result['summary']['total_funcionarios'], 1)
        self.assertEqual(result['summary']['total_movimentacoes'], 1)
        self.assertEqual(result['summary']['data_competencia_arquivo'], "2026-07-01")

        condo = result['condominios'][0]
        self.assertEqual(condo['nome'], "CONJUNTO RESIDENCIAL TRIUMPH")
        self.assertEqual(condo['cnpj'], "12329457000123")
        self.assertEqual(condo['rua'], "RUA TAPAJOS")
        self.assertEqual(condo['numero'], "000061")
        self.assertEqual(condo['bairro'], "TUPI")
        self.assertEqual(condo['cidade'], "PRAIA GRANDE")
        self.assertEqual(condo['estado'], "SP")
        self.assertEqual(condo['cep'], "11703340")

        self.assertEqual(len(condo['funcionarios']), 1)
        func_data = condo['funcionarios'][0]
        self.assertEqual(func_data['nome'], "RICARDO PEREIRA DA SILVA")
        self.assertEqual(func_data['cpf'], "26353372841")
        self.assertEqual(func_data['data_nascimento'], "1977-11-07")

        self.assertEqual(len(func_data['movimentacoes']), 1)
        mov = func_data['movimentacoes'][0]
        self.assertEqual(mov['produto'], "VBA")
        self.assertEqual(mov['codigo_produto'], "VBA")
        self.assertEqual(mov['valor'], Decimal('953.85'))

        if os.path.exists(path):
            os.remove(path)

    def test_beneficio_sem_funcionario_gera_erro(self):
        c10 = make_line()
        c10[0] = '1'
        c10[1] = '0'
        set_slice(c10, 2, 6, '0066')
        set_slice(c10, 6, 20, '23230001400337')
        set_slice(c10, 46, 66, 'CONDOMINIO TESTE')
        condo10 = finalize(c10, 1)

        b = make_line()
        b[0] = '6'
        b[1] = '0'
        set_slice(b, 2, 6, '0066')
        set_slice(b, 6, 16, '2323000140')
        set_slice(b, 16, 19, 'VBA')
        set_slice(b, 19, 30, '16975222703')
        set_slice(b, 70, 81, '00000095385')
        beneficio = finalize(b, 2)

        path = self.write_test_file([condo10, beneficio])
        result = parse_ahreas_layout(path, 1)

        self.assertTrue(
            any("não encontrado" in err for err in result['errors']),
            f"Esperava erro de funcionário não encontrado. Erros: {result['errors']}"
        )
        os.remove(path)

    def test_cpf_invalido_ignorado(self):
        c10 = make_line()
        c10[0] = '1'
        c10[1] = '0'
        set_slice(c10, 2, 6, '0066')
        set_slice(c10, 6, 20, '23230001400337')
        set_slice(c10, 46, 66, 'CONDOMINIO TESTE')
        condo10 = finalize(c10, 1)

        f = make_line()
        f[0] = '3'
        f[1] = '0'
        set_slice(f, 2, 6, '0066')
        set_slice(f, 6, 20, '23230001400000')
        set_slice(f, 16, 27, '00000000000')
        set_slice(f, 27, 31, '0337')
        set_slice(f, 79, 100, 'NOME INVALIDO CPF')
        func = finalize(f, 2)

        path = self.write_test_file([condo10, func])
        result = parse_ahreas_layout(path, 1)

        self.assertTrue(
            any("CPF inválido" in err for err in result['errors']),
            f"Esperava erro de CPF inválido. Erros: {result['errors']}"
        )
        os.remove(path)
