import pandas as pd
import re
from decimal import Decimal, InvalidOperation
from ..RB.parsers import cpf_valido_matematicamente


def parse_excel_layout(file_path, file_upload_id):
    result = {
        "file_upload_id": file_upload_id,
        "condominios": [],
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
        df = pd.read_excel(file_path, dtype={
            'cnpj_condominio': str,
            'cpf_funcionario': str,
            'cep_condominio': str,
            'matricula_funcionario': str,
            'codigo_produto': str
        })

        df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
        df = df.where(pd.notnull(df), None)

        condominios_data = {}

        for index, row in df.iterrows():
            line_num = index + 2

            raw_cpf = re.sub(r'\D', '', str(row.get('cpf_funcionario', '')))
            if not raw_cpf or len(raw_cpf) != 11 or not cpf_valido_matematicamente(raw_cpf):
                result['errors'].append(f"Linha {line_num}: CPF '{raw_cpf}' inválido.")
                continue

            raw_cnpj = re.sub(r'\D', '', str(row.get('cnpj_condominio', '')))
            if not raw_cnpj:
                result['errors'].append(f"Linha {line_num}: CNPJ do condomínio ausente.")
                continue

            try:
                v_total = Decimal(str(row.get('valor_beneficio(total)', 0))).quantize(Decimal('0.00'))
            except (InvalidOperation, ValueError):
                v_total = Decimal('0.00')
                result['errors'].append(f"Linha {line_num}: Valor de benefício inválido.")

            comp = row.get('data_competencia')
            if isinstance(comp, pd.Timestamp):
                data_iso = comp.strftime('%Y-%m-%d')
            else:
                data_iso = str(comp) if comp else None

            matricula = str(row.get('matricula_funcionario', '')).strip()
            nome_func = str(row.get('nome_funcionario', '')).upper()
            departamento = str(row.get('tipo_local_condominio', '')).strip()
            funcao = str(row.get('funcao_funcionario', '')).strip()
            data_nasc = row.get('data_nascimento_funcionario')
            if isinstance(data_nasc, pd.Timestamp):
                data_nasc = data_nasc.strftime('%Y-%m-%d')
            else:
                data_nasc = str(data_nasc) if data_nasc else None
            produto = str(row.get('nome_produto', '')).strip()

            if raw_cnpj not in condominios_data:
                condominios_data[raw_cnpj] = {
                    "nome": str(row.get('nome_condominio', '')).strip(),
                    "cnpj": raw_cnpj,
                    "valor_condo": Decimal('0.00'),
                    "funcionarios": {}
                }

            func_key = f"{raw_cnpj}_{matricula}"
            if func_key not in condominios_data[raw_cnpj]["funcionarios"]:
                condominios_data[raw_cnpj]["funcionarios"][func_key] = {
                    "cpf": raw_cpf,
                    "nome": nome_func,
                    "matricula": matricula,
                    "departamento": departamento,
                    "funcao": funcao,
                    "data_nascimento": data_nasc,
                    "valor_bene": Decimal('0.00'),
                    "movimentacoes": []
                }

            condominios_data[raw_cnpj]["funcionarios"][func_key]["movimentacoes"].append({
                "produto": produto,
                "valor": v_total
            })
            condominios_data[raw_cnpj]["funcionarios"][func_key]["valor_bene"] += v_total
            condominios_data[raw_cnpj]["valor_condo"] += v_total

            result['summary']['valor_total_beneficios'] += v_total
            result['summary']['total_movimentacoes'] += 1

            if not result['summary']['data_competencia_arquivo']:
                result['summary']['data_competencia_arquivo'] = data_iso

        for cnpj, condo_data in condominios_data.items():
            lista_funcionarios = []
            for func_key, func in condo_data["funcionarios"].items():
                lista_funcionarios.append({
                    "nome": func["nome"],
                    "cpf": func["cpf"],
                    "matricula": func["matricula"],
                    "departamento": func["departamento"],
                    "funcao": func["funcao"],
                    "data_nascimento": func["data_nascimento"],
                    "valor_bene": func["valor_bene"],
                    "movimentacoes": func["movimentacoes"]
                })

            result["condominios"].append({
                "nome": condo_data["nome"],
                "cnpj": condo_data["cnpj"],
                "valor_condo": condo_data["valor_condo"],
                "funcionarios": lista_funcionarios
            })

            result['summary']['total_funcionarios'] += len(lista_funcionarios)

        result['summary']['total_condominios'] = len(condominios_data)
        if condominios_data:
            result['summary']['primeiro_cnpj_processado'] = list(condominios_data.keys())[0]

    except Exception as e:
        result['errors'].append(f"Erro ao processar planilha: {str(e)}")

    return result