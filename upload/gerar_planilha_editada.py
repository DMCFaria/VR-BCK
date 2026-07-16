import io
import re
from datetime import datetime
from decimal import Decimal

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side


def gerar_planilha_vr(dados_modificados, data_competencia=None):
    """
    Gera planilha no formato VR Template com dados modificados pelo frontend.

    dados_modificados: {
        "condominios": [
            {
                "cnpj": "...", "nome": "...", "rua": "...", "numero": "...",
                "complemento": "...", "bairro": "...", "cidade": "...",
                "estado": "...", "cep": "...",
                "funcionarios": [
                    {
                        "cpf": "...", "nome": "...", "matricula": "...",
                        "data_nascimento": "...", "sexo": "...",
                        "movimentacoes": [
                            {"produto": "...", "codigo_produto": "...", "valor": 35.00}
                        ]
                    }
                ]
            }
        ]
    }

    Retorna: BytesIO com o arquivo .xlsm
    """
    wb = openpyxl.Workbook()

    # Styles
    font_header = Font(name='Arial', size=10, bold=True)
    font_data = Font(name='Arial', size=10)
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # ========================
    # 1. SHEET SUMARIO
    # ========================
    ws_sum = wb.active
    ws_sum.title = 'Sumario'

    ws_sum.cell(row=1, column=1, value='RESUMO DA IMPORTAÇÃO').font = Font(name='Arial', size=14, bold=True)
    ws_sum.cell(row=3, column=1, value='Data de Competência:').font = font_header

    if data_competencia:
        if isinstance(data_competencia, str):
            ws_sum.cell(row=6, column=1, value=data_competencia).font = font_data
        else:
            ws_sum.cell(row=6, column=1, value=data_competencia.strftime('%d/%m/%Y')).font = font_data
    else:
        ws_sum.cell(row=6, column=1, value=datetime.now().strftime('%d/%m/%Y')).font = font_data

    ws_sum.cell(row=8, column=1, value='Total de Condomínios:').font = font_header
    ws_sum.cell(row=8, column=2, value=len(dados_modificados.get('condominios', []))).font = font_data

    total_func = sum(
        len(c.get('funcionarios', []))
        for c in dados_modificados.get('condominios', [])
    )
    ws_sum.cell(row=9, column=1, value='Total de Funcionários:').font = font_header
    ws_sum.cell(row=9, column=2, value=total_func).font = font_data

    ws_sum.column_dimensions['A'].width = 30
    ws_sum.column_dimensions['B'].width = 20

    # ========================
    # 2. SHEET LOCAL DE ENTREGA
    # ========================
    ws_locais = wb.create_sheet('Local de Entrega')

    headers_locais = [
        'Código Local Entrega', 'Nome', 'Tipo Endereço',
        'Endereço', 'Número', 'Complemento', 'Bairro',
        'Cidade', 'Estado', 'CEP'
    ]
    for col_idx, header in enumerate(headers_locais, start=1):
        cell = ws_locais.cell(row=1, column=col_idx, value=header)
        cell.font = font_header
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        cell.border = thin_border

    for row_idx, condo in enumerate(dados_modificados.get('condominios', []), start=2):
        cnpj = ''.join(filter(str.isdigit, str(condo.get('cnpj', ''))))
        ws_locais.cell(row=row_idx, column=1, value=cnpj).font = font_data
        ws_locais.cell(row=row_idx, column=2, value=condo.get('nome', '')).font = font_data
        ws_locais.cell(row=row_idx, column=3, value='AV').font = font_data
        ws_locais.cell(row=row_idx, column=4, value=condo.get('rua', '')).font = font_data
        ws_locais.cell(row=row_idx, column=5, value=condo.get('numero', '')).font = font_data
        ws_locais.cell(row=row_idx, column=6, value=condo.get('complemento', '')).font = font_data
        ws_locais.cell(row=row_idx, column=7, value=condo.get('bairro', '')).font = font_data
        ws_locais.cell(row=row_idx, column=8, value=condo.get('cidade', '')).font = font_data
        ws_locais.cell(row=row_idx, column=9, value=condo.get('estado', '')).font = font_data
        ws_locais.cell(row=row_idx, column=10, value=condo.get('cep', '')).font = font_data

        for col_idx in range(1, 11):
            ws_locais.cell(row=row_idx, column=col_idx).border = thin_border

    col_widths_locais = [25, 40, 12, 40, 10, 20, 30, 30, 8, 12]
    for i, width in enumerate(col_widths_locais, start=1):
        ws_locais.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width

    # ========================
    # 3. SHEET BENEFICIARIO
    # ========================
    ws_ben = wb.create_sheet('Beneficiario')

    # Coletar todos os produtos únicos
    produtos_unicos = []
    produtos_vistos = set()
    for condo in dados_modificados.get('condominios', []):
        for func in condo.get('funcionarios', []):
            for mov in func.get('movimentacoes', []):
                prod_nome = mov.get('produto', '')
                if prod_nome and prod_nome not in produtos_vistos:
                    produtos_unicos.append(prod_nome)
                    produtos_vistos.add(prod_nome)

    # Headers fixos
    headers_fixos = [
        'CPF*', 'Código local entrega*', 'Código centro de custo',
        'Matrícula', 'Nome completo*', 'Nome Impressão Cartão',
        'Data Nascimento*', 'Sexo', 'Faixa Salarial'
    ]

    for col_idx, header in enumerate(headers_fixos, start=1):
        cell = ws_ben.cell(row=1, column=col_idx, value=header)
        cell.font = font_header
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        cell.border = thin_border

    # Headers de produto na linha 2
    prod_start_col = len(headers_fixos) + 1
    for i, prod_nome in enumerate(produtos_unicos):
        col_idx = prod_start_col + i
        cell = ws_ben.cell(row=2, column=col_idx, value=f'{prod_nome}\nValor do crédito\nInserir valor')
        cell.font = font_header
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        cell.border = thin_border

    # Preencher dados dos funcionários
    row_num = 3
    for condo in dados_modificados.get('condominios', []):
        cnpj = ''.join(filter(str.isdigit, str(condo.get('cnpj', ''))))

        for func in condo.get('funcionarios', []):
            cpf = ''.join(filter(str.isdigit, str(func.get('cpf', '')))).zfill(11)
            data_nasc = func.get('data_nascimento', '')
            if data_nasc and isinstance(data_nasc, str):
                # Tentar converter de YYYY-MM-DD para DDMMYYYY
                try:
                    dt = datetime.strptime(data_nasc, '%Y-%m-%d')
                    data_nasc = dt.strftime('%d%m%Y')
                except ValueError:
                    pass
            elif data_nasc and hasattr(data_nasc, 'strftime'):
                data_nasc = data_nasc.strftime('%d%m%Y')

            # Dados fixos
            ws_ben.cell(row=row_num, column=1, value=cpf).font = font_data
            ws_ben.cell(row=row_num, column=2, value=cnpj).font = font_data
            ws_ben.cell(row=row_num, column=3, value='').font = font_data
            ws_ben.cell(row=row_num, column=4, value=func.get('matricula', '')).font = font_data
            ws_ben.cell(row=row_num, column=5, value=func.get('nome', '')).font = font_data
            ws_ben.cell(row=row_num, column=6, value='').font = font_data
            ws_ben.cell(row=row_num, column=7, value=data_nasc).font = font_data
            ws_ben.cell(row=row_num, column=8, value=func.get('sexo', '')).font = font_data
            ws_ben.cell(row=row_num, column=9, value='').font = font_data

            for col_idx in range(1, 10):
                ws_ben.cell(row=row_num, column=col_idx).border = thin_border

            # Preencher valores de produto
            for mov in func.get('movimentacoes', []):
                prod_nome = mov.get('produto', '')
                valor = mov.get('valor', 0)
                if prod_nome in produtos_vistos:
                    col_idx = prod_start_col + produtos_unicos.index(prod_nome)
                    cell = ws_ben.cell(row=row_num, column=col_idx, value=float(valor))
                    cell.font = font_data
                    cell.number_format = '#,##0.00'
                    cell.border = thin_border

            row_num += 1

    # Ajustar larguras das colunas
    col_widths_ben = [15, 25, 20, 12, 40, 25, 18, 8, 15]
    for i, width in enumerate(col_widths_ben, start=1):
        ws_ben.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width
    for i in range(len(produtos_unicos)):
        ws_ben.column_dimensions[openpyxl.utils.get_column_letter(prod_start_col + i)].width = 20

    # Salvar em BytesIO
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
