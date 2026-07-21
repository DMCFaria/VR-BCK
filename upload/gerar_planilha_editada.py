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
    logger.info(f"[EDITAR_PLANILHA] dados_modificados presente: {bool(dados_modificados)}")
    logger.debug(f"[EDITAR_PLANILHA] data_competencia: {data_competencia}")

    if not dados_modificados:
        logger.warning("[EDITAR_PLANILHA] dados_modificados está vazio ou nulo")
        return None

    if not os.path.exists(file_path):
        logger.error(f"[EDITAR_PLANILHA] Arquivo não encontrado: {file_path}")
        return None

    try:
        condominios = dados_modificados.get('condominios', [])
        total_funcionarios = sum(len(c.get('funcionarios', [])) for c in condominios)
        logger.info(f"[EDITAR_PLANILHA] Dados recebidos - condominios: {len(condominios)}, funcionarios: {total_funcionarios}")

        file_ext = os.path.splitext(file_path)[1].lower()
        keep_vba = file_ext == '.xlsm'
        logger.debug(f"[EDITAR_PLANILHA] Extensão do arquivo: {file_ext}, keep_vba: {keep_vba}")

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


def _set_cell_value(ws, row, column, value):
    """
    Define o valor de uma célula, desviando para a célula superior-esquerda
    caso o destino seja uma MergedCell (somente leitura no openpyxl).
    """
    cell = ws.cell(row=row, column=column)
    if isinstance(cell, openpyxl.cell.cell.MergedCell):
        for merged_range in ws.merged_cells.ranges:
            if cell.row >= merged_range.min_row and cell.row <= merged_range.max_row \
                    and cell.column >= merged_range.min_col and cell.column <= merged_range.max_col:
                top_left = merged_range.start_cell
                ws.cell(row=top_left.row, column=top_left.column, value=value)
                logger.debug(f"[EDITAR_PLANILHA] Valor '{value}' escrito na célula mesclada {top_left.coordinate} (requisitado {cell.coordinate})")
                return
    else:
        cell.value = value


def _editar_sheet_sumario(wb, dados_modificados, data_competencia):
    if 'Sumario' not in wb.sheetnames:
        logger.warning("[EDITAR_PLANILHA] Sheet 'Sumario' não encontrada")
        return

    ws = wb['Sumario']
    logger.debug("[EDITAR_PLANILHA] Editando sheet 'Sumario'")

    if data_competencia:
        valor_competencia = data_competencia if isinstance(data_competencia, str) else data_competencia.strftime('%d/%m/%Y')
        _set_cell_value(ws, row=6, column=1, value=valor_competencia)
        logger.debug(f"[EDITAR_PLANILHA] Sumario - competência atualizada: {valor_competencia}")

    total_condos = len(dados_modificados.get('condominios', []))
    total_func = sum(len(c.get('funcionarios', [])) for c in dados_modificados.get('condominios', []))

    _set_cell_value(ws, row=8, column=2, value=total_condos)
    _set_cell_value(ws, row=9, column=2, value=total_func)

    logger.info(f"[EDITAR_PLANILHA] Sumario atualizado: {total_condos} condominios, {total_func} funcionarios")


def _editar_sheet_local_entrega(wb, dados_modificados):
    if 'Local de Entrega' not in wb.sheetnames:
        logger.warning("[EDITAR_PLANILHA] Sheet 'Local de Entrega' não encontrada")
        return

    ws = wb['Local de Entrega']
    logger.debug("[EDITAR_PLANILHA] Editando sheet 'Local de Entrega'")

    max_row = ws.max_row
    if max_row > 1:
        ws.delete_rows(2, max_row - 1)
        logger.debug(f"[EDITAR_PLANILHA] Local de Entrega - {max_row - 1} linhas antigas removidas")

    for row_idx, condo in enumerate(dados_modificados.get('condominios', []), start=2):
        cnpj = ''.join(filter(str.isdigit, str(condo.get('cnpj', ''))))
        _set_cell_value(ws, row=row_idx, column=1, value=cnpj)
        _set_cell_value(ws, row=row_idx, column=2, value=condo.get('nome', ''))
        _set_cell_value(ws, row=row_idx, column=3, value='AV')
        _set_cell_value(ws, row=row_idx, column=4, value=condo.get('rua', ''))
        _set_cell_value(ws, row=row_idx, column=5, value=condo.get('numero', ''))
        _set_cell_value(ws, row=row_idx, column=6, value=condo.get('complemento', ''))
        _set_cell_value(ws, row=row_idx, column=7, value=condo.get('bairro', ''))
        _set_cell_value(ws, row=row_idx, column=8, value=condo.get('cidade', ''))
        _set_cell_value(ws, row=row_idx, column=9, value=condo.get('estado', ''))
        _set_cell_value(ws, row=row_idx, column=10, value=condo.get('cep', ''))
        logger.debug(f"[EDITAR_PLANILHA] Local de Entrega - linha {row_idx}: cnpj={cnpj}, nome={condo.get('nome', '')}, cep={condo.get('cep', '')}")

    logger.info(f"[EDITAR_PLANILHA] Local de Entrega atualizado: {len(dados_modificados.get('condominios', []))} linhas")


def _editar_sheet_beneficiario(wb, dados_modificados):
    if 'Beneficiario' not in wb.sheetnames:
        logger.warning("[EDITAR_PLANILHA] Sheet 'Beneficiario' não encontrada")
        return

    ws = wb['Beneficiario']
    logger.debug("[EDITAR_PLANILHA] Editando sheet 'Beneficiario'")

    col_produtos = _ler_headers_produtos(ws)
    logger.debug(f"[EDITAR_PLANILHA] Headers de produtos mapeados: {col_produtos}")

    max_row = ws.max_row
    if max_row > 2:
        ws.delete_rows(3, max_row - 2)
        logger.debug(f"[EDITAR_PLANILHA] Beneficiario - {max_row - 2} linhas antigas removidas")

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

            _set_cell_value(ws, row=row_num, column=1, value=cpf)
            _set_cell_value(ws, row=row_num, column=2, value=cnpj)
            _set_cell_value(ws, row=row_num, column=3, value='')
            _set_cell_value(ws, row=row_num, column=4, value=func.get('matricula', ''))
            _set_cell_value(ws, row=row_num, column=5, value=func.get('nome', ''))
            _set_cell_value(ws, row=row_num, column=6, value='')
            _set_cell_value(ws, row=row_num, column=7, value=data_nasc)
            _set_cell_value(ws, row=row_num, column=8, value=func.get('sexo', ''))
            _set_cell_value(ws, row=row_num, column=9, value='')

            logger.debug(f"[EDITAR_PLANILHA] Beneficiario - linha {row_num}: cpf={cpf}, cnpj={cnpj}, nome={func.get('nome', '')}, matricula={func.get('matricula', '')}, data_nasc={data_nasc}")

            for mov in func.get('movimentacoes', []):
                prod_nome = mov.get('produto', '')
                valor = mov.get('valor', 0)

                col_idx = _encontrar_coluna_produto(col_produtos, prod_nome)
                if col_idx:
                    _set_cell_value(ws, row=row_num, column=col_idx, value=float(valor))
                    logger.debug(f"[EDITAR_PLANILHA] Beneficiario - produto '{prod_nome}' na coluna {col_idx}, valor {valor}")
                else:
                    logger.warning(f"[EDITAR_PLANILHA] Beneficiario - produto '{prod_nome}' não encontrado nas colunas mapeadas")

            row_num += 1

    logger.info(f"[EDITAR_PLANILHA] Beneficiario atualizado: {row_num - 3} funcionarios")


def _ler_headers_produtos(ws):
    col_produtos = {}
    header_row = list(ws.iter_rows(min_row=2, max_row=2, values_only=True))
    if not header_row:
        logger.warning("[EDITAR_PLANILHA] Nenhum header de produto encontrado na linha 2 do sheet 'Beneficiario'")
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
            logger.debug(f"[EDITAR_PLANILHA] Header exato mapeado - coluna {col_idx}: {h}")
        else:
            for nome in COLUNAS_PRODUTO:
                if nome.lower() in h.lower() or h.lower() in nome.lower():
                    col_produtos[col_idx] = nome
                    logger.debug(f"[EDITAR_PLANILHA] Header aproximado mapeado - coluna {col_idx}: '{h}' -> '{nome}'")
                    break

    logger.info(f"[EDITAR_PLANILHA] Total de headers de produtos mapeados: {len(col_produtos)}")
    return col_produtos


def _encontrar_coluna_produto(col_produtos, nome_produto):
    if not nome_produto:
        logger.debug("[EDITAR_PLANILHA] Nome do produto vazio ao buscar coluna")
        return None

    for col_idx, nome in col_produtos.items():
        if nome == nome_produto:
            logger.debug(f"[EDITAR_PLANILHA] Produto '{nome_produto}' encontrado na coluna {col_idx} (correspondência exata)")
            return col_idx

    nome_lower = nome_produto.lower()
    for col_idx, nome in col_produtos.items():
        if nome.lower() in nome_lower or nome_lower in nome.lower():
            logger.debug(f"[EDITAR_PLANILHA] Produto '{nome_produto}' encontrado na coluna {col_idx} (correspondência parcial com '{nome}')")
            return col_idx

    logger.debug(f"[EDITAR_PLANILHA] Produto '{nome_produto}' não mapeado em nenhuma coluna")
    return None
