import io
import os
import logging
from datetime import datetime
from decimal import Decimal

import openpyxl

logger = logging.getLogger(__name__)

COLUNAS_PRODUTO = {
    'Refeição': '207', 'Multi Refeição': '207', 'Alimentação': '27',
    'Multi Alimentação': '27', 'Auto': '28', 'Mobilidade': '28',
    'VR Mobilidade': '28', 'Multi Mobilidade': '28', 'VR Multi Mobilidade': '28',
    'Cesta': '201', 'Boas Festas': '202', 'Auxílio Alimentação': '204',
    'Multi Auxílio Alimentação': '204', 'Auxílio Refeição': '207',
    'Multi Auxílio Refeição': '207', 'Multibenefício': '207', 'Multibenefícios': '207',
    'Auxílio VR+VA': '207', 'Multi Auxílio VR+VA': '207', 'Multi Premiação': '207',
    'VR Refeição': '207', 'VR Alimentação': '27', 'VR Auto': '28',
    'VR Alimentação Cesta': '201', 'VR Boas Festas': '202', 'VR Auxílio Alimentação': '204',
    'VR Auxílio Refeição': '207', 'VR Multibenefícios': '207', 'VR+VA': '207',
    'VR Multi Refeição': '207', 'VR Multi Alimentação': '27',
    'VR Multi Alimentação Valor do crédito': '27',
    'VR Multi Refeição Auxílio': '207', 'VR Multi Alimentação Auxílio': '204',
    'VR Multi VR+VA': '207',
}


def editar_planilha_original(file_path, dados_modificados, data_competencia=None):
    """
    Edita a planilha original preservando formatação e macros.
    
    Abre o arquivo original, limpa as linhas de dados e preenche
    com os dados modificados, mantendo headers, formatação e macros VBA.
    
    Retorna: BytesIO com o arquivo editado
    """
    logger.info(f"[EDITAR_PLANILHA] Iniciando edição da planilha original: {file_path}")
    logger.info(f"[EDITAR_PLANILHA] dados_modificados: {bool(dados_modificados)}")

    if not dados_modificados:
        logger.warning("[EDITAR_PLANILHA] dados_modificados está vazio ou nulo")
        return None

    if not os.path.exists(file_path):
        logger.error(f"[EDITAR_PLANILHA] Arquivo não encontrado: {file_path}")
        return None

    try:
        file_ext = os.path.splitext(file_path)[1].lower()
        keep_vba = file_ext == '.xlsm'

        wb = openpyxl.load_workbook(file_path, keep_vba=keep_vba)
        logger.info(f"[EDITAR_PLANILHA] Planilha aberta - sheets: {wb.sheetnames}")

        _editar_sheet_sumario(wb, dados_modificados, data_competencia)
        _editar_sheet_local_entrega(wb, dados_modificados)
        _editar_sheet_beneficiario(wb, dados_modificados)

        output = io.BytesIO()
        wb.save(output)
        wb.close()
        output.seek(0)

        logger.info(f"[EDITAR_PLANILHA] Planilha editada com sucesso - tamanho: {output.getbuffer().nbytes} bytes")
        return output

    except Exception as e:
        logger.error(f"[EDITAR_PLANILHA] Erro ao editar planilha: {str(e)}", exc_info=True)
        return None


def _editar_sheet_sumario(wb, dados_modificados, data_competencia):
    if 'Sumario' not in wb.sheetnames:
        logger.warning("[EDITAR_PLANILHA] Sheet 'Sumario' não encontrada")
        return

    ws = wb['Sumario']

    if data_competencia:
        if isinstance(data_competencia, str):
            ws.cell(row=6, column=1, value=data_competencia)
        else:
            ws.cell(row=6, column=1, value=data_competencia.strftime('%d/%m/%Y'))

    total_condos = len(dados_modificados.get('condominios', []))
    total_func = sum(len(c.get('funcionarios', [])) for c in dados_modificados.get('condominios', []))

    ws.cell(row=8, column=2, value=total_condos)
    ws.cell(row=9, column=2, value=total_func)

    logger.info(f"[EDITAR_PLANILHA] Sumario atualizado: {total_condos} condominios, {total_func} funcionarios")


def _editar_sheet_local_entrega(wb, dados_modificados):
    if 'Local de Entrega' not in wb.sheetnames:
        logger.warning("[EDITAR_PLANILHA] Sheet 'Local de Entrega' não encontrada")
        return

    ws = wb['Local de Entrega']

    max_row = ws.max_row
    if max_row > 1:
        ws.delete_rows(2, max_row - 1)

    for row_idx, condo in enumerate(dados_modificados.get('condominios', []), start=2):
        cnpj = ''.join(filter(str.isdigit, str(condo.get('cnpj', ''))))
        ws.cell(row=row_idx, column=1, value=cnpj)
        ws.cell(row=row_idx, column=2, value=condo.get('nome', ''))
        ws.cell(row=row_idx, column=3, value='AV')
        ws.cell(row=row_idx, column=4, value=condo.get('rua', ''))
        ws.cell(row=row_idx, column=5, value=condo.get('numero', ''))
        ws.cell(row=row_idx, column=6, value=condo.get('complemento', ''))
        ws.cell(row=row_idx, column=7, value=condo.get('bairro', ''))
        ws.cell(row=row_idx, column=8, value=condo.get('cidade', ''))
        ws.cell(row=row_idx, column=9, value=condo.get('estado', ''))
        ws.cell(row=row_idx, column=10, value=condo.get('cep', ''))

    logger.info(f"[EDITAR_PLANILHA] Local de Entrega atualizado: {len(dados_modificados.get('condominios', []))} linhas")


def _editar_sheet_beneficiario(wb, dados_modificados):
    if 'Beneficiario' not in wb.sheetnames:
        logger.warning("[EDITAR_PLANILHA] Sheet 'Beneficiario' não encontrada")
        return

    ws = wb['Beneficiario']

    col_produtos = _ler_headers_produtos(ws)

    max_row = ws.max_row
    if max_row > 2:
        ws.delete_rows(3, max_row - 2)

    row_num = 3
    for condo in dados_modificados.get('condominios', []):
        cnpj = ''.join(filter(str.isdigit, str(condo.get('cnpj', ''))))

        for func in condo.get('funcionarios', []):
            cpf = ''.join(filter(str.isdigit, str(func.get('cpf', '')))).zfill(11)
            data_nasc = func.get('data_nascimento', '')
            if data_nasc and isinstance(data_nasc, str):
                try:
                    dt = datetime.strptime(data_nasc, '%Y-%m-%d')
                    data_nasc = dt.strftime('%d%m%Y')
                except ValueError:
                    pass
            elif data_nasc and hasattr(data_nasc, 'strftime'):
                data_nasc = data_nasc.strftime('%d%m%Y')

            ws.cell(row=row_num, column=1, value=cpf)
            ws.cell(row=row_num, column=2, value=cnpj)
            ws.cell(row=row_num, column=3, value='')
            ws.cell(row=row_num, column=4, value=func.get('matricula', ''))
            ws.cell(row=row_num, column=5, value=func.get('nome', ''))
            ws.cell(row=row_num, column=6, value='')
            ws.cell(row=row_num, column=7, value=data_nasc)
            ws.cell(row=row_num, column=8, value=func.get('sexo', ''))
            ws.cell(row=row_num, column=9, value='')

            for mov in func.get('movimentacoes', []):
                prod_nome = mov.get('produto', '')
                valor = mov.get('valor', 0)

                col_idx = _encontrar_coluna_produto(col_produtos, prod_nome)
                if col_idx:
                    ws.cell(row=row_num, column=col_idx, value=float(valor))

            row_num += 1

    logger.info(f"[EDITAR_PLANILHA] Beneficiario atualizado: {row_num - 3} funcionarios")


def _ler_headers_produtos(ws):
    col_produtos = {}
    header_row = list(ws.iter_rows(min_row=2, max_row=2, values_only=True))
    if not header_row:
        return col_produtos

    header_row = header_row[0]
    for col_idx, val in enumerate(header_row, start=1):
        if val is None:
            continue
        h = str(val).strip().split('\n')[0].strip()
        if not h:
            continue
        if h in COLUNAS_PRODUTO:
            col_produtos[col_idx] = h
        else:
            for nome in COLUNAS_PRODUTO:
                if nome.lower() in h.lower() or h.lower() in nome.lower():
                    col_produtos[col_idx] = nome
                    break

    return col_produtos


def _encontrar_coluna_produto(col_produtos, nome_produto):
    if not nome_produto:
        return None

    for col_idx, nome in col_produtos.items():
        if nome == nome_produto:
            return col_idx

    nome_lower = nome_produto.lower()
    for col_idx, nome in col_produtos.items():
        if nome.lower() in nome_lower or nome_lower in nome.lower():
            return col_idx

    return None
