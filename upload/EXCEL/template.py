import io
import pandas as pd
from django.http import HttpResponse
from rest_framework.decorators import api_view

COLUNAS = [
    'cnpj_condominio', 'nome_condominio', 'tipo_local_condominio',
    'endereco_condominio', 'numero_condominio', 'complemento_condominio',
    'bairro_condominio', 'cidade_condominio', 'estado_condominio',
    'cep_condominio', 'cpf_funcionario', 'matricula_funcionario',
    'nome_funcionario', 'funcao_funcionario', 'data_nascimento_funcionario',
    'sexo_funcionario', 'cep_funcionario', 'endereco_rua_funcionario',
    'endereco_numero_funcionario', 'endereco_complemento_funcionario',
    'endereco_bairro_funcionario',
    'codigo_produto', 'nome_produto',
    'data_competencia', 'valor_beneficio(total)', 'quantidade_dias'
]

COLUNAS_REQUIRED = {
    'cnpj_condominio', 'nome_condominio', 'cpf_funcionario',
    'nome_funcionario', 'matricula_funcionario',
    'valor_beneficio(total)', 'data_competencia',
}

COLUNAS_DESCRICAO = {
    'cnpj_condominio': 'CNPJ do condomínio (apenas números)',
    'nome_condominio': 'Nome/Razão social do condomínio',
    'tipo_local_condominio': 'Departamento / tipo do local',
    'endereco_condominio': 'Logradouro do condomínio',
    'numero_condominio': 'Número do endereço do condomínio',
    'complemento_condominio': 'Complemento do endereço do condomínio',
    'bairro_condominio': 'Bairro do condomínio',
    'cidade_condominio': 'Cidade do condomínio',
    'estado_condominio': 'UF do condomínio (sigla, ex: SP)',
    'cep_condominio': 'CEP do condomínio (apenas números)',
    'cpf_funcionario': 'CPF do funcionário (apenas números, 11 dígitos)',
    'matricula_funcionario': 'Matrícula do funcionário',
    'nome_funcionario': 'Nome completo do funcionário',
    'funcao_funcionario': 'Cargo / função do funcionário',
    'data_nascimento_funcionario': 'Data de nascimento (dd/mm/aaaa)',
    'sexo_funcionario': 'Sexo (M/F)',
    'cep_funcionario': 'CEP do funcionário (apenas números)',
    'endereco_rua_funcionario': 'Logradouro do funcionário',
    'endereco_numero_funcionario': 'Número do endereço do funcionário',
    'endereco_complemento_funcionario': 'Complemento do endereço do funcionário',
    'endereco_bairro_funcionario': 'Bairro do funcionário',
    'codigo_produto': 'Código do produto VR',
    'nome_produto': 'Nome do produto (ex: VR Refeição, VR Alimentação)',
    'data_competencia': 'Data de competência (dd/mm/aaaa)',
    'valor_beneficio(total)': 'Valor total do benefício em R$',
    'quantidade_dias': 'Quantidade de dias (opcional)',
}


def _add_instrucoes_sheet(workbook, writer):
    sheet = workbook.add_worksheet('Instruções')
    
    fmt_title = workbook.add_format({
        'bold': True, 'font_size': 14, 'font_color': '#1f4e78',
        'bottom': 2, 'bottom_color': '#1f4e78'
    })
    fmt_subtitle = workbook.add_format({
        'bold': True, 'font_size': 11, 'font_color': '#1f4e78'
    })
    fmt_text = workbook.add_format({'font_size': 10, 'text_wrap': True})
    fmt_bold = workbook.add_format({'bold': True, 'font_size': 10})
    fmt_required = workbook.add_format({
        'font_size': 10, 'font_color': '#c0392b', 'bold': True
    })
    fmt_header_inst = workbook.add_format({
        'bold': True, 'bg_color': '#1f4e78', 'font_color': 'white',
        'border': 1, 'text_wrap': True
    })
    fmt_row_col = workbook.add_format({
        'border': 1, 'text_wrap': True, 'font_size': 10
    })
    fmt_row_req = workbook.add_format({
        'border': 1, 'text_wrap': True, 'font_size': 10,
        'bg_color': '#fde8e8'
    })

    sheet.set_column('A:A', 8)
    sheet.set_column('B:B', 30)
    sheet.set_column('C:C', 14)
    sheet.set_column('D:D', 50)

    sheet.write(0, 0, '📋 Instruções para Importação', fmt_title)
    sheet.merge_range(0, 0, 0, 3, '📋 Instruções para Importação', fmt_title)
    
    row = 2
    sheet.write(row, 0, 'Este template deve ser preenchido seguindo as orientações abaixo:', fmt_text)
    row += 2
    
    sheet.write(row, 0, '⚙️ Regras Gerais', fmt_subtitle)
    row += 1
    rules = [
        '• Preencha uma linha por funcionário por produto.',
        '• Campos marcados com * são obrigatórios. O sistema rejeitará linhas com esses campos ausentes ou inválidos.',
        '• Não altere os nomes das colunas — o sistema depende deles para processar os dados.',
        '• O CPF deve conter exatamente 11 dígitos numéricos (sem pontos ou traços).',
        '• O CNPJ deve conter exatamente 14 dígitos numéricos (sem pontos ou traços).',
        '• Datas devem estar no formato dd/mm/aaaa (ex: 31/12/2025).',
        '• Valores monetários devem ser numéricos (ex: 1500,50).',
        '• CEP, CPF, CNPJ e matrícula devem ser preenchidos apenas com números.',
        '• O valor total por funcionário não pode ultrapassar R$ 2.499,99.',
    ]
    for rule in rules:
        sheet.write(row, 0, rule, fmt_text)
        row += 1
    
    row += 1
    sheet.write(row, 0, '📌 Descrição das Colunas', fmt_subtitle)
    row += 1
    
    headers_inst = ['Coluna', 'Nome do Campo', 'Obrigatório', 'Descrição']
    for col_num, header in enumerate(headers_inst):
        sheet.write(row, col_num, header, fmt_header_inst)
    row += 1

    for col_name in COLUNAS:
        is_req = col_name in COLUNAS_REQUIRED
        fmt_row = fmt_row_req if is_req else fmt_row_col
        req_text = 'Sim *' if is_req else 'Não'
        req_fmt = fmt_required if is_req else fmt_text
        
        sheet.write(row, 0, chr(65 + COLUNAS.index(col_name)), fmt_row)
        sheet.write(row, 1, col_name, fmt_row)
        sheet.write(row, 2, req_text, fmt_row)
        sheet.write(row, 3, COLUNAS_DESCRICAO.get(col_name, ''), fmt_row)
        row += 1
    
    row += 2
    sheet.write(row, 0, '💡 Dicas', fmt_subtitle)
    row += 1
    tips = [
        '• Recomendamos abrir este arquivo no Microsoft Excel ou LibreOffice Calc.',
        '• Após preencher, salve o arquivo no formato .xlsx antes de enviar.',
        '• Se encontrar erros no upload, o sistema informará quais linhas precisam ser corrigidas.',
        '• Para dúvidas, entre em contato com o suporte.',
    ]
    for tip in tips:
        sheet.write(row, 0, tip, fmt_text)
        row += 1


@api_view(['GET'])
def baixar_template_excel(request):
    df = pd.DataFrame(columns=COLUNAS)
    
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Importacao_Completa')
        
        workbook  = writer.book
        worksheet = writer.sheets['Importacao_Completa']
        
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#1f4e78', 'font_color': 'white',
            'border': 1, 'text_wrap': True, 'valign': 'vcenter',
            'align': 'center'
        })
        header_req_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#1f4e78', 'font_color': '#f8d7da',
            'border': 1, 'text_wrap': True, 'valign': 'vcenter',
            'align': 'center'
        })
        text_fmt = workbook.add_format({'num_format': '@'})
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        money_fmt = workbook.add_format({'num_format': 'R$ #,##0.00'})

        for col_num, value in enumerate(df.columns.values):
            if value in COLUNAS_REQUIRED:
                worksheet.write(0, col_num, f'{value}*', header_req_fmt)
            else:
                worksheet.write(0, col_num, value, header_fmt)

        for col in ['A:A', 'J:J', 'K:L', 'Q:Q', 'V:V']:
            worksheet.set_column(col, 22, text_fmt)

        for col in ['O:O', 'X:X']:
            worksheet.set_column(col, 18, date_fmt)

        worksheet.set_column('Y:Y', 18, money_fmt)

        worksheet.set_column('B:B', 35)
        worksheet.set_column('M:M', 35)

        worksheet.set_column('Q:Q', 20)
        worksheet.set_column('R:R', 40)
        worksheet.set_column('S:S', 15)
        worksheet.set_column('T:T', 28)
        worksheet.set_column('U:U', 28)

        worksheet.set_column('A:A', 20)
        worksheet.set_column('C:C', 22)
        worksheet.set_column('D:D', 35)
        worksheet.set_column('E:E', 15)
        worksheet.set_column('F:F', 22)
        worksheet.set_column('G:G', 22)
        worksheet.set_column('H:H', 25)
        worksheet.set_column('I:I', 8)
        worksheet.set_column('N:N', 25)
        worksheet.set_column('P:P', 8)
        worksheet.set_column('W:W', 25)
        worksheet.set_column('Z:Z', 15)

        worksheet.autofilter(0, 0, 0, len(COLUNAS) - 1)
        worksheet.freeze_panes(1, 0)

        _add_instrucoes_sheet(workbook, writer)

    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="modelo_importacao_vr_completo.xlsx"'
    
    return response