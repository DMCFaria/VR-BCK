import re
import os
from decimal import Decimal, InvalidOperation
from datetime import datetime


COL_SEQUENCIAL = slice(0, 5)
COL_TIPO_REGISTRO_WIDER = slice(5, 6)
COL_CNPJ = slice(6, 20)

COL_CONDOMINIO_RAZAO_SOCIAL = slice(20, 60)

COL_ENDERECO_RUA = slice(31, 85)
COL_ENDERECO_NUMERO = slice(91, 105)
COL_ENDERECO_COMPLEMENTO = slice(106, 130)
COL_ENDERECO_BAIRRO = slice(130, 150)
COL_ENDERECO_CIDADE = slice(170, 190)
COL_ENDERECO_ESTADO = slice(211, 213)
COL_ENDERECO_CEP = slice(23, 30)



COL_FUNCIONARIO_MATRICULA = slice(19, 32)
COL_FUNCIONARIO_NOME = slice(32, 72)
COL_FUNCIONARIO_DEPARTAMENTO = slice(92, 102)
COL_FUNCIONARIO_FUNCAO = slice(132, 139)
COL_FUNCIONARIO_DATA_NASC = slice(172, 180)
COL_FUNCIONARIO_CPF = slice(183, 194)

COL_BENEFICIO_MATRICULA = slice(19, 32)
COL_BENEFICIO_NUM_DIAS = slice(100, 104)
COL_BENEFICIO_VALOR = slice(109, 116)
COL_BENEFICIO_PRODUTO = slice(44, 88)
COL_CODIGO_PRODUTO = slice(40, 45)


def format_valor_rb(text):
    if not text:
        return Decimal('0.00')
    digits = re.sub(r'\D', '', text.strip())
    if not digits:
        return Decimal('0.00')
    try:
        return Decimal(digits) / Decimal('100.00')
    except:
        return Decimal('0.00')


def parse_data_nascimento(text):
    if not text or len(text.strip()) < 8:
        return None, "DATA_NASCIMENTO_INVALIDA"
    raw = re.sub(r'\D', '', text.strip()[:8])
    if len(raw) == 8 and raw.isdigit():
        try:
            dia = int(raw[0:2])
            mes = int(raw[2:4])
            ano = int(raw[4:8])
            if 1900 <= ano <= 2100 and 1 <= mes <= 12 and 1 <= dia <= 31:
                return f"{ano}-{mes:02d}-{dia:02d}", None
            return None, "DATA_NASCIMENTO_INVALIDA"
        except:
            return None, "DATA_NASCIMENTO_INVALIDA"
    return None, "DATA_NASCIMENTO_INVALIDA"


def extrair_cpf_estrito(line):
    raw = re.sub(r'\D', '', line[COL_FUNCIONARIO_CPF].strip())
    if not raw or len(raw) != 11:
        return None
    if cpf_valido_matematicamente(raw):
        return raw
    return None


def parse_rb_layout(file_path, file_upload_id):
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

    if not os.path.exists(file_path):
        result['errors'].append("Arquivo não encontrado.")
        return result

    try:
        condominios_data = {}
        current_cnpj = None
        data_competencia = None

        with open(file_path, 'r', encoding='latin-1') as f:
            for i, line in enumerate(f):
                if len(line.strip()) < 10:
                    continue
                line_num = i + 1

                tipo = line[COL_TIPO_REGISTRO_WIDER].strip()

                if tipo == '0':
                    match = re.search(r'(\d{8})', line)
                    if match:
                        d = match.group(1)
                        if d.startswith('20'):
                            data_competencia = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
                        else:
                            data_competencia = f"{d[4:8]}-{d[2:4]}-{d[0:2]}"
                        result['summary']['data_competencia_arquivo'] = data_competencia

                elif tipo == '1':
                    cnpj = re.sub(r'\D', '', line[COL_CNPJ].strip())
                    if cnpj and len(cnpj) != 14:
                        result['errors'].append(f"Linha {line_num}: CNPJ com tamanho inválido ({len(cnpj)} dígitos).")
                        result['linhas_com_erro'].append({
                            "tipo_erro": "CNPJ_TAMANHO_INVALIDO",
                            "linha": line_num,
                            "dados": {
                                "nome": line[COL_CONDOMINIO_RAZAO_SOCIAL].strip()
                            }
                        })
                        current_cnpj = None
                        continue
                    elif cnpj:
                        current_cnpj = cnpj
                        nome_condo = line[COL_CONDOMINIO_RAZAO_SOCIAL].strip()
                        if cnpj not in condominios_data:
                            condominios_data[cnpj] = {
                                "nome": nome_condo,
                                "cnpj": cnpj,
                                "valor_condo": Decimal('0.00'),
                                "funcionarios": {}
                            }
                    else:
                        result['errors'].append(f"Linha {line_num}: CNPJ ausente/inválido.")
                        result['linhas_com_erro'].append({
                            "tipo_erro": "CNPJ_INVALIDO",
                            "linha": line_num,
                            "dados": {
                                "nome": line[COL_CONDOMINIO_RAZAO_SOCIAL].strip()
                            }
                        })
                        current_cnpj = None
                        continue
                #CAPTURAR O ENDERECO DO CONDOMINIO
                elif tipo == '2':
                    cnpj = re.sub(r'\D', '', line[COL_CNPJ].strip())
                    if cnpj and cnpj in condominios_data:
                        condominios_data[cnpj]["endereco"] = line[COL_ENDERECO_RUA].strip()
                        condominios_data[cnpj]["numero"] = line[COL_ENDERECO_NUMERO].strip()
                        condominios_data[cnpj]["complemento"] = line[COL_ENDERECO_COMPLEMENTO].strip()
                        condominios_data[cnpj]["bairro"] = line[COL_ENDERECO_BAIRRO].strip()
                        condominios_data[cnpj]["cidade"] = line[COL_ENDERECO_CIDADE].strip()
                        condominios_data[cnpj]["estado"] = line[COL_ENDERECO_ESTADO].strip()
                        condominios_data[cnpj]["cep"] = line[COL_ENDERECO_CEP].strip()

                elif tipo == '3':
                    mat = line[COL_FUNCIONARIO_MATRICULA].strip()
                    nome = line[COL_FUNCIONARIO_NOME].strip()
                    cpf = extrair_cpf_estrito(line)
                    departamento = line[COL_FUNCIONARIO_DEPARTAMENTO].strip()
                    funcao = line[COL_FUNCIONARIO_FUNCAO].strip()
                    data_nasc, erro_data = parse_data_nascimento(line[COL_FUNCIONARIO_DATA_NASC])

                    if not cpf:
                        result['errors'].append(f"Linha {line_num}: CPF inválido.")
                        result['linhas_com_erro'].append({
                            "tipo_erro": "CPF_INVALIDO",
                            "linha": line_num,
                            "dados": {
                                "cnpj": current_cnpj,
                                "matricula": mat,
                                "nome": nome
                            }
                        })
                        continue

                    if current_cnpj and current_cnpj in condominios_data:
                        if mat not in condominios_data[current_cnpj]["funcionarios"]:
                            condominios_data[current_cnpj]["funcionarios"][mat] = {
                                "cpf": cpf,
                                "nome": nome,
                                "matricula": mat,
                                "departamento": departamento,
                                "funcao": funcao,
                                "data_nascimento": data_nasc,
                                "valor_bene": Decimal('0.00'),
                                "movimentacoes": []
                            }
                            
                            if erro_data:
                                result['errors'].append(f"Linha {line_num}: Data de nascimento inválida.")
                                result['linhas_com_erro'].append({
                                    "tipo_erro": "DATA_NASCIMENTO_INVALIDA",
                                    "linha": line_num,
                                    "dados": {
                                        "cpf": cpf,
                                        "nome": nome,
                                        "matricula": mat
                                    }
                                })
                    else:
                        result['errors'].append(f"Linha {line_num}: CNPJ não encontrado.")
                        result['linhas_com_erro'].append({
                            "tipo_erro": "CNPJ_NAO_CADASTRADO",
                            "linha": line_num,
                            "dados": {
                                "cpf": cpf,
                                "nome": nome,
                                "matricula": mat
                            }
                        })

                elif tipo == '4':
                    mat = line[COL_BENEFICIO_MATRICULA].strip()
                    if not current_cnpj or current_cnpj not in condominios_data:
                        result['errors'].append(f"Linha {line_num}: CNPJ não encontrado.")
                        result['linhas_com_erro'].append({
                            "tipo_erro": "CNPJ_NAO_CADASTRADO",
                            "linha": line_num,
                            "dados": {
                                "matricula": mat
                            }
                        })
                        continue
                    if mat not in condominios_data[current_cnpj]["funcionarios"]:
                        result['errors'].append(f"Linha {line_num}: Matrícula {mat} não encontrada.")
                        continue

                    v_unit = format_valor_rb(line[COL_BENEFICIO_VALOR])
                    qtd_raw = re.sub(r'\D', '', line[COL_BENEFICIO_NUM_DIAS].strip())
                    qtd = int(qtd_raw) if (qtd_raw and int(qtd_raw) > 0) else 1
                    v_total = v_unit * qtd
                    produto = line[COL_BENEFICIO_PRODUTO].strip()
                    codigo_produto = line[COL_CODIGO_PRODUTO].strip()

                    func_data = condominios_data[current_cnpj]["funcionarios"][mat]
                    func_cpf = func_data.get("cpf", "")
                    func_data["movimentacoes"].append({
                        "produto": produto,
                        "codigo_produto": codigo_produto,
                        "valor": v_total
                    })
                    func_data["valor_bene"] += v_total
                    condominios_data[current_cnpj]["valor_condo"] += v_total

                    result['summary']['valor_total_beneficios'] += v_total
                    result['summary']['total_movimentacoes'] += 1
                    
                    if func_data["valor_bene"] > Decimal('2499.99'):
                        result['errors'].append(f"Linha {line_num}: Valor total do funcionário R$ {func_data['valor_bene']} excede limite de R$ 2499,99.")
                        result['linhas_com_erro'].append({
                            "tipo_erro": "VALOR_EXCEDIDO",
                            "linha": line_num,
                            "dados": {
                                "cpf": func_cpf,
                                "nome": func_data["nome"],
                                "matricula": mat,
                                "valor_total": str(func_data["valor_bene"])
                            }
                        })

        for cnpj, condo_data in condominios_data.items():
            lista_funcionarios = []
            for mat, func in condo_data["funcionarios"].items():
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

            condo_entry = {
                "nome": condo_data["nome"],
                "cnpj": condo_data["cnpj"],
                "valor_condo": condo_data["valor_condo"],
                "rua": condo_data.get("endereco"),
                "numero": condo_data.get("numero"),
                "complemento": condo_data.get("complemento"),
                "bairro": condo_data.get("bairro"),
                "cidade": condo_data.get("cidade"),
                "estado": condo_data.get("estado"),
                "cep": condo_data.get("cep"),
                "funcionarios": lista_funcionarios
            }
            result["condominios"].append(condo_entry)

            result['summary']['total_funcionarios'] += len(lista_funcionarios)

        result['summary']['total_condominios'] = len(condominios_data)
        if condominios_data:
            result['summary']['primeiro_cnpj_processado'] = list(condominios_data.keys())[0]

    except Exception as e:
        result['errors'].append(f"Erro fatal: {str(e)}")

    return result




def cpf_valido_matematicamente(cpf: str) -> bool:
    """
    Valida o CPF usando o cálculo dos dígitos verificadores.
    """
    # Remove qualquer coisa que não seja número
    cpf = re.sub(r'\D', '', cpf)

    # Verifica se tem 11 dígitos ou se é uma sequência repetida (inválida)
    if len(cpf) != 11 or cpf in [s * 11 for s in "0123456789"]:
        return False

    # Validação do primeiro dígito
    soma = 0
    for i in range(9):
        soma += int(cpf[i]) * (10 - i)
    resto = soma % 11
    dv1 = 0 if resto < 2 else 11 - resto
    if int(cpf[9]) != dv1:
        return False

    # Validação do segundo dígito
    soma = 0
    for i in range(10):
        soma += int(cpf[i]) * (11 - i)
    resto = soma % 11
    dv2 = 0 if resto < 2 else 11 - resto
    if int(cpf[10]) != dv2:
        return False

    return True