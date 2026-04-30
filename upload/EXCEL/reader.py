import pandas as pd
import re
from decimal import Decimal, InvalidOperation
from ..RB.parsers import cpf_valido_matematicamente
import openpyxl

def parse_excel_layout(file_path, file_upload_id):
    result = {
        "file_upload_id": file_upload_id,
        "condominios": [],
        "errors": [],
        "linhas_com_erro": [],
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
            'codigo_produto': str,
            'cep_funcionario': str,
            'endereco_rua_funcionario': str,
            'endereco_numero_funcionario': str,
            'endereco_complemento_funcionario': str,
            'endereco_bairro_funcionario': str
        })

        df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
        df = df.where(pd.notnull(df), None)

        condominios_data = {}

        for index, row in df.iterrows():
            line_num = index + 2

            raw_cpf = re.sub(r'\D', '', str(row.get('cpf_funcionario', '')))
            if raw_cpf and len(raw_cpf) != 11:
                result['errors'].append(f"Linha {line_num}: CPF com tamanho inválido ({len(raw_cpf)} dígitos).")
                result['linhas_com_erro'].append({
                    "tipo_erro": "CPF_TAMANHO_INVALIDO",
                    "linha": line_num,
                    "dados": {
                        "cpf": str(row.get('cpf_funcionario', '')),
                        "cnpj": str(row.get('cnpj_condominio', '')),
                        "nome_funcionario": str(row.get('nome_funcionario', '')),
                        "matricula": str(row.get('matricula_funcionario', ''))
                    }
                })
                continue
            elif not raw_cpf or not cpf_valido_matematicamente(raw_cpf):
                result['errors'].append(f"Linha {line_num}: CPF '{raw_cpf}' inválido.")
                result['linhas_com_erro'].append({
                    "tipo_erro": "CPF_INVALIDO",
                    "linha": line_num,
                    "dados": {
                        "cnpj": str(row.get('cnpj_condominio', '')),
                        "nome_funcionario": str(row.get('nome_funcionario', '')),
                        "matricula": str(row.get('matricula_funcionario', ''))
                    }
                })
                continue

            raw_cnpj = re.sub(r'\D', '', str(row.get('cnpj_condominio', '')))
            if not raw_cnpj:
                result['errors'].append(f"Linha {line_num}: CNPJ do condomínio ausente.")
                result['linhas_com_erro'].append({
                    "tipo_erro": "CNPJ_INVALIDO",
                    "linha": line_num,
                    "dados": {
                        "nome_condominio": str(row.get('nome_condominio', '')),
                        "nome_funcionario": str(row.get('nome_funcionario', ''))
                    }
                })
                continue
            
            if len(raw_cnpj) != 14:
                result['errors'].append(f"Linha {line_num}: CNPJ com tamanho inválido ({len(raw_cnpj)} dígitos).")
                result['linhas_com_erro'].append({
                    "tipo_erro": "CNPJ_TAMANHO_INVALIDO",
                    "linha": line_num,
                    "dados": {
                        "cnpj": str(row.get('cnpj_condominio', '')),
                        "nome_condominio": str(row.get('nome_condominio', ''))
                    }
                })
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
            if data_nasc is None or str(data_nasc).strip() in ['', 'None', 'nan']:
                data_nasc_validada = None
            elif isinstance(data_nasc, pd.Timestamp):
                data_nasc_validada = data_nasc.strftime('%Y-%m-%d')
            else:
                data_nasc_str = str(data_nasc).strip()
                try:
                    from datetime import datetime
                    parsed = datetime.strptime(data_nasc_str, '%Y-%m-%d')
                    data_nasc_validada = parsed.strftime('%Y-%m-%d')
                except:
                    try:
                        from datetime import datetime
                        parsed = datetime.strptime(data_nasc_str, '%d/%m/%Y')
                        data_nasc_validada = parsed.strftime('%Y-%m-%d')
                    except:
                        data_nasc_validada = None
            
            produto = str(row.get('nome_produto', '')).strip()
            codigo_produto = str(row.get('codigo_produto', '')).strip() or None

            if raw_cnpj not in condominios_data:
                condominios_data[raw_cnpj] = {
                    "nome": str(row.get('nome_condominio', '')).strip(),
                    "cnpj": raw_cnpj,
                    "valor_condo": Decimal('0.00'),
                    "rua": str(row.get('endereco_condominio', '')).strip(),
                    "numero": str(row.get('numero_condominio', '')).strip(),
                    "complemento": str(row.get('complemento_condominio', '')).strip(),
                    "bairro": str(row.get('bairro_condominio', '')).strip(),
                    "cidade": str(row.get('cidade_condominio', '')).strip(),
                    "estado": str(row.get('estado_condominio', '')).strip(),
                    "cep": str(row.get('cep_condominio', '')).strip(),
                    "funcionarios": {}
                }

            func_key = f"{raw_cnpj}_{matricula}"
            if func_key not in condominios_data[raw_cnpj]["funcionarios"]:
                func_data = {
                    "cpf": raw_cpf,
                    "nome": nome_func,
                    "matricula": matricula,
                    "departamento": departamento,
                    "funcao": funcao,
                    "data_nascimento": data_nasc_validada,
                    "cep": str(row.get('cep_funcionario', '')).strip() or None,
                    "endereco_rua": str(row.get('endereco_rua_funcionario', '')).strip() or None,
                    "endereco_numero": str(row.get('endereco_numero_funcionario', '')).strip() or None,
                    "endereco_complemento": str(row.get('endereco_complemento_funcionario', '')).strip() or None,
                    "endereco_bairro": str(row.get('endereco_bairro_funcionario', '')).strip() or None,
                    "valor_bene": Decimal('0.00'),
                    "movimentacoes": []
                }
                
                if data_nasc_validada is None:
                    result['errors'].append(f"Linha {line_num}: Data de nascimento inválida.")
                    result['linhas_com_erro'].append({
                        "tipo_erro": "DATA_NASCIMENTO_INVALIDA",
                        "linha": line_num,
                        "dados": {
                            "cpf": raw_cpf,
                            "nome_funcionario": nome_func,
                            "matricula": matricula
                        }
                    })
                
                condominios_data[raw_cnpj]["funcionarios"][func_key] = func_data

            condominios_data[raw_cnpj]["funcionarios"][func_key]["movimentacoes"].append({
                "produto": produto,
                "codigo_produto": codigo_produto,
                "valor": v_total
            })
            condominios_data[raw_cnpj]["funcionarios"][func_key]["valor_bene"] += v_total
            condominios_data[raw_cnpj]["valor_condo"] += v_total

            result['summary']['valor_total_beneficios'] += v_total
            result['summary']['total_movimentacoes'] += 1
            
            if condominios_data[raw_cnpj]["funcionarios"][func_key]["valor_bene"] > Decimal('2499.99'):
                result['errors'].append(f"Linha {line_num}: Valor total do funcionário R$ {condominios_data[raw_cnpj]['funcionarios'][func_key]['valor_bene']} excede limite de R$ 2499,99.")
                result['linhas_com_erro'].append({
                    "tipo_erro": "VALOR_EXCEDIDO",
                    "linha": line_num,
                    "dados": {
                        "cpf": raw_cpf,
                        "nome_funcionario": nome_func,
                        "matricula": matricula,
                        "valor_total": str(condominios_data[raw_cnpj]["funcionarios"][func_key]["valor_bene"])
                    }
                })

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
                "rua": condo_data.get("rua"),
                "numero": condo_data.get("numero"),
                "bairro": condo_data.get("bairro"),
                "cidade": condo_data.get("cidade"),
                "estado": condo_data.get("estado"),
                "cep": condo_data.get("cep"),
                "funcionarios": lista_funcionarios
            })

            result['summary']['total_funcionarios'] += len(lista_funcionarios)

        result['summary']['total_condominios'] = len(condominios_data)
        if condominios_data:
            result['summary']['primeiro_cnpj_processado'] = list(condominios_data.keys())[0]

    except Exception as e:
        result['errors'].append(f"Erro ao processar planilha: {str(e)}")

    return result