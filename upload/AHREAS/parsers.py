import os
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
from ..RB.parsers import cpf_valido_matematicamente


COL_CONDO_NOME = slice(46, 86)
COL_CONDO_CNPJ = slice(46, 60)

COL_LOGRADOURO_TIPO = slice(126, 130)
COL_LOGRADOURO_NOME = slice(146, 186)
COL_NUMERO = slice(186, 192)
COL_BAIRRO = slice(212, 242)
COL_CIDADE = slice(242, 272)
COL_ESTADO = slice(272, 274)
COL_CEP = slice(274, 282)

COL_FUNC_CPF = slice(16, 27)
COL_FUNC_CODIGO_CONDO = slice(27, 31)
COL_FUNC_NOME = slice(79, 119)
COL_FUNC_DATA_NASC = slice(143, 151)

COL_BENEF_PRODUTO = slice(16, 19)
COL_BENEF_CPF = slice(19, 30)
COL_BENEF_VALOR = slice(70, 81)

COL_COMPET_DATA = slice(19, 27)
COL_COMPET_PRODUTO = slice(16, 19)

SEQUENCIAL_FIM = slice(341, 350)


def format_valor_ahreas(text):
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
        return None
    raw = re.sub(r'\D', '', text.strip()[:8])
    if len(raw) == 8 and raw.isdigit():
        try:
            dia = int(raw[0:2])
            mes = int(raw[2:4])
            ano = int(raw[4:8])
            if 1900 <= ano <= 2100 and 1 <= mes <= 12 and 1 <= dia <= 31:
                return f"{ano}-{mes:02d}-{dia:02d}"
        except:
            pass
    return None


def parse_ahreas_layout(file_path, file_upload_id, valor_max_beneficio=None):
    if valor_max_beneficio is None:
        valor_max_beneficio = Decimal('2499.99')

    result = {
        "file_upload_id": file_upload_id,
        "condominios": [],
        "errors": [],
        "linhas_com_erro": [],
        "summary": {
            "administradora_id": None,
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
        condominios_map = {}
        current_codigo = None
        current_condo_cnpj = None

        with open(file_path, 'r', encoding='latin-1') as f:
            for i, line in enumerate(f):
                line = line.rstrip('\n')
                if len(line.strip()) < 10:
                    continue
                line_num = i + 1
                tipo = line[0]

                # HEADER - extrai CNPJ da empresa (não usado no resultado)
                if tipo == '0':
                    pass

                # CONDOMINIO PRINCIPAL
                elif tipo == '1':
                    sub = line[1] if len(line) > 1 else ''
                    codigo = line[16:20]

                    if sub == '0':
                        nome = line[COL_CONDO_NOME].strip()
                        current_codigo = codigo

                        endereco = line[COL_LOGRADOURO_TIPO].strip()
                        rua = line[COL_LOGRADOURO_NOME].strip()
                        numero = line[COL_NUMERO].strip()
                        bairro = line[COL_BAIRRO].strip()
                        cidade = line[COL_CIDADE].strip()
                        estado = line[COL_ESTADO].strip()
                        cep = line[COL_CEP].strip()

                        if codigo not in condominios_map:
                            condominios_map[codigo] = {
                                "nome": nome,
                                "cnpj": "",
                                "valor_condo": Decimal('0.00'),
                                "rua": f"{endereco} {rua}".strip() if endereco else rua,
                                "numero": numero,
                                "complemento": "",
                                "bairro": bairro,
                                "cidade": cidade,
                                "estado": estado,
                                "cep": cep,
                                "funcionarios": {}
                            }

                    elif sub == '1':
                        cnpj = re.sub(r'\D', '', line[COL_CONDO_CNPJ])
                        if codigo in condominios_map:
                            condominios_map[codigo]["cnpj"] = cnpj
                        else:
                            condominios_map[codigo] = {
                                "nome": "",
                                "cnpj": cnpj,
                                "valor_condo": Decimal('0.00'),
                                "rua": "", "numero": "", "complemento": "",
                                "bairro": "", "cidade": "", "estado": "", "cep": "",
                                "funcionarios": {}
                            }

                # FUNCIONARIO
                elif tipo == '3':
                    cpf = re.sub(r'\D', '', line[COL_FUNC_CPF])
                    nome = line[COL_FUNC_NOME].strip()
                    codigo = line[COL_FUNC_CODIGO_CONDO].strip()
                    data_nasc = parse_data_nascimento(line[COL_FUNC_DATA_NASC])

                    if not cpf or len(cpf) != 11 or not cpf_valido_matematicamente(cpf):
                        result['errors'].append(f"Linha {line_num}: CPF inválido.")
                        result['linhas_com_erro'].append({
                            "tipo_erro": "CPF_INVALIDO",
                            "linha": line_num,
                            "dados": {"nome": nome}
                        })
                        continue

                    if codigo not in condominios_map:
                        result['errors'].append(f"Linha {line_num}: Condomínio código {codigo} não encontrado.")
                        result['linhas_com_erro'].append({
                            "tipo_erro": "CONDOMINIO_NAO_ENCONTRADO",
                            "linha": line_num,
                            "dados": {"cpf": cpf, "nome": nome}
                        })
                        continue

                    if cpf not in condominios_map[codigo]["funcionarios"]:
                        condominios_map[codigo]["funcionarios"][cpf] = {
                            "cpf": cpf,
                            "nome": nome,
                            "matricula": "",
                            "departamento": "",
                            "funcao": "",
                            "data_nascimento": data_nasc,
                            "valor_bene": Decimal('0.00'),
                            "movimentacoes": []
                        }

                # COMPETENCIA / LOTE
                elif tipo == '5':
                    data_raw = line[COL_COMPET_DATA].strip()
                    if len(data_raw) == 8 and data_raw.isdigit():
                        dia = int(data_raw[0:2])
                        mes = int(data_raw[2:4])
                        ano = int(data_raw[4:8])
                        if 1900 <= ano <= 2100 and 1 <= mes <= 12 and 1 <= dia <= 31:
                            result['summary']['data_competencia_arquivo'] = f"{ano}-{mes:02d}-{dia:02d}"

                # BENEFICIO
                elif tipo == '6':
                    cpf = re.sub(r'\D', '', line[COL_BENEF_CPF])
                    produto = line[COL_BENEF_PRODUTO].strip()
                    valor = format_valor_ahreas(line[COL_BENEF_VALOR])

                    if not cpf or len(cpf) != 11 or not cpf_valido_matematicamente(cpf):
                        result['errors'].append(f"Linha {line_num}: CPF inválido no benefício.")
                        result['linhas_com_erro'].append({
                            "tipo_erro": "CPF_INVALIDO",
                            "linha": line_num,
                            "dados": {"cpf": cpf}
                        })
                        continue

                    # Find the funcionario across all condominios
                    found = False
                    for codigo, condo_data in condominios_map.items():
                        if cpf in condo_data["funcionarios"]:
                            func_data = condo_data["funcionarios"][cpf]
                            func_data["movimentacoes"].append({
                                "produto": produto,
                                "codigo_produto": produto,
                                "valor": valor
                            })
                            func_data["valor_bene"] += valor
                            condo_data["valor_condo"] += valor
                            result['summary']['valor_total_beneficios'] += valor
                            result['summary']['total_movimentacoes'] += 1

                            if func_data["valor_bene"] > valor_max_beneficio:
                                result['errors'].append(
                                    f"Linha {line_num}: Valor total do funcionário R$ {func_data['valor_bene']} "
                                    f"excede limite de R$ {valor_max_beneficio}."
                                )
                                result['linhas_com_erro'].append({
                                    "tipo_erro": "VALOR_EXCEDIDO",
                                    "linha": line_num,
                                    "dados": {
                                        "cpf": cpf,
                                        "nome": func_data["nome"],
                                        "matricula": "",
                                        "valor_total": str(func_data["valor_bene"])
                                    }
                                })
                            found = True
                            break

                    if not found:
                        result['errors'].append(f"Linha {line_num}: Funcionário CPF {cpf} não encontrado.")
                        result['linhas_com_erro'].append({
                            "tipo_erro": "FUNCIONARIO_NAO_ENCONTRADO",
                            "linha": line_num,
                            "dados": {"cpf": cpf}
                        })

                elif tipo == '9':
                    pass

        for codigo, condo_data in condominios_map.items():
            lista_funcionarios = []
            for cpf, func in condo_data["funcionarios"].items():
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
                "rua": condo_data.get("rua"),
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

        result['summary']['total_condominios'] = len(condominios_map)
        if condominios_map:
            first = list(condominios_map.values())[0]
            result['summary']['primeiro_cnpj_processado'] = first.get("cnpj") or "N/A"

    except Exception as e:
        result['errors'].append(f"Erro fatal: {str(e)}")

    return result
