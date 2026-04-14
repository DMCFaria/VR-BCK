import pandas as pd
import re
from decimal import Decimal, InvalidOperation
from ..RB.parsers import cpf_valido_matematicamente



def parse_excel_layout(file_path, file_upload_id):
    result = {
        "file_upload_id": file_upload_id,
        "movimentacoes_detalhada": [],
        "errors": [],
        "summary": {
            "total_condominios": 0,
            "total_funcionarios": 0,
            "total_movimentacoes": 0,
            "valor_total_beneficios": Decimal('0.00'),
            "data_competencia_arquivo": None,
            "primeiro_cnpj_processado": "N/A"
        }
    }

    try:
        # 1. Leitura do Excel forçando tipos críticos para evitar perda de zeros à esquerda
        df = pd.read_excel(file_path, dtype={
            'cnpj_condominio': str,
            'cpf_funcionario': str,
            'cep_condominio': str,
            'matricula_funcionario': str,
            'codigo_produto': str
        })

        # Limpeza básica: remover espaços em branco de strings e trocar NaN por None
        df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
        df = df.where(pd.notnull(df), None)

        cnpjs_vistos = []
        cpfs_vistos = set()

        for index, row in df.iterrows():
            line_num = index + 2  # Excel começa em 1 + cabeçalho
            
            # --- Validação de CPF (Mesma lógica estrita do TXT) ---
            raw_cpf = re.sub(r'\D', '', str(row.get('cpf_funcionario', '')))
            if not raw_cpf or len(raw_cpf) != 11 or not cpf_valido_matematicamente(raw_cpf):
                result['errors'].append(f"Linha {line_num}: CPF '{raw_cpf}' inválido.")
                continue

            # --- Validação de CNPJ ---
            raw_cnpj = re.sub(r'\D', '', str(row.get('cnpj_condominio', '')))
            if not raw_cnpj:
                result['errors'].append(f"Linha {line_num}: CNPJ do condomínio ausente.")
                continue

            # --- Tratamento de Valor ---
            try:
                v_total = Decimal(str(row.get('valor_beneficio(total)', 0))).quantize(Decimal('0.00'))
            except (InvalidOperation, ValueError):
                v_total = Decimal('0.00')
                result['errors'].append(f"Linha {line_num}: Valor de benefício inválido.")

            # --- Data de Competência ---
            # Se for objeto datetime do pandas, converte para string ISO
            comp = row.get('data_competencia')
            if isinstance(comp, pd.Timestamp):
                data_iso = comp.strftime('%Y-%m-%d')
            else:
                data_iso = str(comp) if comp else None

            # 2. Montagem da Movimentação (Exato formato do Parser TXT)
            result['movimentacoes_detalhada'].append({
                "cpf_func": raw_cpf,
                "nome_func": str(row.get('nome_funcionario', '')).upper(),
                "valor_recarga_bene": v_total,
                "cnpj": raw_cnpj,
                "vencimento": data_iso
            })

            # 3. Atualização de Sumários e Contadores
            if raw_cnpj not in cnpjs_vistos:
                cnpjs_vistos.append(raw_cnpj)
            
            cpfs_vistos.add(raw_cpf)
            result['summary']['valor_total_beneficios'] += v_total
            result['summary']['total_movimentacoes'] += 1
            
            # Define a competência global baseada na primeira linha válida, se ainda não houver
            if not result['summary']['data_competencia_arquivo']:
                result['summary']['data_competencia_arquivo'] = data_iso

        # Finalização do Sumário
        result['summary']['total_condominios'] = len(cnpjs_vistos)
        result['summary']['total_funcionarios'] = len(cpfs_vistos)
        if cnpjs_vistos:
            result['summary']['primeiro_cnpj_processado'] = cnpjs_vistos[0]

    except Exception as e:
        result['errors'].append(f"Erro ao processar planilha: {str(e)}")

    return result