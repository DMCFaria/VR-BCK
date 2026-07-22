import os
import unittest
from decimal import Decimal

from upload.EXCEL.reader2 import parse_fut_template


class Reader2HomeOfficeTest(unittest.TestCase):
    """Testes para o parser de planilhas VR."""

    def test_multi_home_office_sem_hifen_eh_reconhecido(self):
        """
        Planilhas que usam 'Multi Home office' (sem hífen) devem reconhecer
        o produto e não retornar erro de 'nenhum benefício preenchido'.
        """
        file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'VR - ADM E CONDS.xlsm'
        )
        if not os.path.exists(file_path):
            self.skipTest(f'Arquivo de exemplo não encontrado: {file_path}')

        data = parse_fut_template(
            file_path,
            file_upload_id=1491,
            valor_max_beneficio=Decimal('9999.99'),
            administradora_cnpj='35315360000167',
        )

        self.assertEqual(data.get('status'), None)
        self.assertEqual(len(data.get('linhas_com_erro', [])), 0)
        self.assertEqual(data['summary']['total_funcionarios'], 287)
        self.assertEqual(data['summary']['total_movimentacoes'], 321)

        # Conta movimentações de home office
        home_office_count = 0
        for c in data.get('condominios', []):
            for f in c.get('funcionarios', []):
                for m in f.get('movimentacoes', []):
                    if m.get('tipo') == 'Multi - Home Office':
                        home_office_count += 1

        self.assertEqual(home_office_count, 45)

    def test_produtos_rejeitados_geram_erro(self):
        """
        Colunas de produtos rejeitados (Cultura, Multi Premiação) devem gerar
        erro claro quando possuem valores maiores que zero.
        """
        import openpyxl
        import shutil
        import tempfile

        src = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'VR - ADM E CONDS.xlsm'
        )
        if not os.path.exists(src):
            self.skipTest(f'Arquivo de exemplo não encontrado: {src}')

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'test_rejeicao.xlsm')
            shutil.copy(src, test_file)

            wb = openpyxl.load_workbook(test_file, data_only=False, keep_vba=True)
            ws = wb['Beneficiario']
            # Coluna Cultura (col 13) na linha 7
            ws.cell(7, 13).value = 100.0
            # Coluna Multi Premiação (col 27) na linha 8
            ws.cell(8, 27).value = 200.0
            wb.save(test_file)

            data = parse_fut_template(
                test_file,
                file_upload_id=1492,
                valor_max_beneficio=Decimal('9999.99'),
                administradora_cnpj='35315360000167',
            )

            self.assertEqual(data.get('status'), 'ERRO')
            erros_por_linha = {
                e['linha']: e['erros']
                for e in data.get('linhas_com_erro', [])
            }
            self.assertIn(7, erros_por_linha)
            self.assertIn(8, erros_por_linha)
            self.assertTrue(
                any('Cultura' in err for err in erros_por_linha[7]),
                f'Esperado erro de Cultura na linha 7: {erros_por_linha[7]}'
            )
            self.assertTrue(
                any('Premiação' in err for err in erros_por_linha[8]),
                f'Esperado erro de Premiação na linha 8: {erros_por_linha[8]}'
            )


if __name__ == '__main__':
    unittest.main()
