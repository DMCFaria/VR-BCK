import io
import pandas as pd
from django.http import HttpResponse
from rest_framework.decorators import api_view

@api_view(['GET'])
def baixar_template_excel(request):
    # Lista exata dos seus campos
    colunas = [
        'cnpj_condominio', 'nome_condominio', 'tipo_local_condominio',
        'endereco_condominio', 'numero_condominio', 'complemento_condominio',
        'bairro_condominio', 'cidade_condominio', 'estado_condominio',
        'cep_condominio', 'cpf_funcionario', 'matricula_funcionario',
        'nome_funcionario', 'funcao_funcionario', 'data_nascimento_funcionario',
        'sexo_funcionario', 'cep_funcionario', 'endereco_rua_funcionario',
        'endereco_numero_funcionario', 'endereco_complemento_funcionario', 'endereco_bairro_funcionario',
        'codigo_produto', 'nome_produto',
        'data_competencia', 'valor_beneficio(total)', 'quantidade_dias'
    ]
    
    # Criar DataFrame vazio
    df = pd.DataFrame(columns=colunas)
    
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Importacao_Completa')
        
        workbook  = writer.book
        worksheet = writer.sheets['Importacao_Completa']
        
        # Formatações Críticas
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#1f4e78', 'font_color': 'white', 'border': 1})
        text_fmt = workbook.add_format({'num_format': '@'})  # Força Texto
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy'}) # Data
        money_fmt = workbook.add_format({'num_format': 'R$ #,##0.00'}) # Moeda

        # Aplicar Cabeçalho
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)

        # --- REGRAS POR COLUNA ---
        
        # 1. Colunas que DEVEM ser texto (para não perder o zero à esquerda)
        # cnpj (A), cep_condominio (J), cpf (K), matricula (L), cep_funcionario (Q), codigo_produto (V)
        for col in ['A:A', 'J:J', 'K:L', 'Q:Q', 'V:V']:
            worksheet.set_column(col, 20, text_fmt)

        # 2. Colunas de Datas
        # data_nascimento (O), data_competencia (X)
        for col in ['O:O', 'X:X']:
            worksheet.set_column(col, 18, date_fmt)

        # 3. Coluna de Valor (Y)
        worksheet.set_column('Y:Y', 18, money_fmt)

        # 4. Ajuste de largura para os nomes (B e M)
        worksheet.set_column('B:B', 35) # Nome Condominio
        worksheet.set_column('M:M', 35) # Nome Funcionario

        # 5. Colunas de endereço do funcionário (Q, R, S, T, U)
        worksheet.set_column('Q:Q', 20) # CEP Funcionario
        worksheet.set_column('R:R', 40) # Endereço Rua
        worksheet.set_column('S:S', 15) # Número
        worksheet.set_column('T:T', 30) # Complemento
        worksheet.set_column('U:U', 30) # Bairro

    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="modelo_importacao_vr_completo.xlsx"'
    
    return response