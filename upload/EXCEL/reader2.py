import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
import openpyxl


CODIGO_PRODUTO_PADRAO = '207'

COLUNAS_PRODUTO = {
    # ===== Sem prefixo "VR " (VR-exemplo.xlsm / Template_VR_OLD.xlsx) =====
    'Refeição': CODIGO_PRODUTO_PADRAO,
    'Multi Refeição': CODIGO_PRODUTO_PADRAO,
    'Alimentação': '27',
    'Multi Alimentação': '27',
    'Auto': '28',
    'Cesta': '201',
    'Boas Festas': '202',
    'Auxílio Alimentação': '204',
    'Multi Auxílio Alimentação': '204',
    'Auxílio Refeição': CODIGO_PRODUTO_PADRAO,
    'Multi Auxílio Refeição': CODIGO_PRODUTO_PADRAO,
    'Multibenefício': CODIGO_PRODUTO_PADRAO,
    'Multibenefícios': CODIGO_PRODUTO_PADRAO,
    'Auxílio VR+VA': CODIGO_PRODUTO_PADRAO,
    'Multi Auxílio VR+VA': CODIGO_PRODUTO_PADRAO,
    'Multi Premiação': CODIGO_PRODUTO_PADRAO,
    # ===== Com prefixo "VR " (Template_VR.xlsm) =====
    'VR Refeição': CODIGO_PRODUTO_PADRAO,
    'VR Alimentação': '27',
    'VR Auto': '28',
    'VR Alimentação Cesta': '201',
    'VR Boas Festas': '202',
    'VR Auxílio Alimentação': '204',
    'VR Auxílio Refeição': CODIGO_PRODUTO_PADRAO,
    'VR Multibenefícios': CODIGO_PRODUTO_PADRAO,
    'VR+VA': CODIGO_PRODUTO_PADRAO,
    'VR Multi Refeição': CODIGO_PRODUTO_PADRAO,
    'VR Multi Alimentação': '27',
    'VR Multi Alimentação Valor do crédito': '27',
    'VR Multi Refeição Auxílio': CODIGO_PRODUTO_PADRAO,
    'VR Multi Alimentação Auxílio': '204',
    'VR Multi VR+VA': CODIGO_PRODUTO_PADRAO,
}

# Sheets 60/99/etc são para geração do TXT via VBA - não precisam ser lidas
# Focus: Local de Entrega, Beneficiario, Sumario


def _safe_str(val, default=''):
    if val is None:
        return default
    s = str(val).strip()
    if s.lower() in ('none', 'nan', ''):
        return default
    return s


def _parse_date(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime('%Y-%m-%d')
    s = str(val).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%d%m%Y'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except:
            pass
    return None


def parse_fut_template(file_path, file_upload_id, valor_max_beneficio=None):
    if valor_max_beneficio is None:
        valor_max_beneficio = Decimal('9999.99')

    result = {
        "file_upload_id": file_upload_id,
        "condominios": [],
        "errors": [],
        "linhas_com_erro": [],
        "erros_condominios": [],
        "summary": {
            "total_condominios": 0,
            "total_funcionarios": 0,
            "total_movimentacoes": 0,
            "valor_total_beneficios": Decimal('0.00'),
            "data_competencia_arquivo": None,
            "primeiro_cnpj_processado": "N/A",
        },
    }

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True, keep_vba=False)
    except Exception as e:
        result['errors'].append(f"Erro ao abrir planilha: {str(e)}")
        return result

    # ========================
    # 1. LER SUMARIO
    # ========================
    ws_sum = wb['Sumario']
    data_disponivel = ''
    for row in ws_sum.iter_rows(min_row=6, max_row=6):
        cells = list(row)
        if len(cells) >= 15:
            data_disponivel = _safe_str(cells[14].value or cells[2].value or '')
        elif len(cells) >= 3:
            data_disponivel = _safe_str(cells[2].value or '')

    result['summary']['data_competencia_arquivo'] = _parse_date(data_disponivel)

    # ========================
    # 2. LER LOCAIS DE ENTREGA (condominios)
    # ========================
    ws_locais = wb['Local de Entrega']
    locais = {}  # codigo_local -> dados

    for row in ws_locais.iter_rows(min_row=2, values_only=True):
        codigo = _safe_str(row[0])
        if not codigo:
            continue

        locais[codigo] = {
            "nome": _safe_str(row[1]) if len(row) > 1 else codigo,
            "cnpj": codigo,
            "valor_condo": Decimal('0.00'),
            "rua": _safe_str(row[3]) if len(row) > 3 else '',
            "numero": _safe_str(row[4]) if len(row) > 4 else '',
            "complemento": _safe_str(row[5]) if len(row) > 5 else '',
            "bairro": _safe_str(row[6]) if len(row) > 6 else '',
            "cidade": _safe_str(row[7]) if len(row) > 7 else '',
            "estado": _safe_str(row[8]) if len(row) > 8 else '',
            "cep": _safe_str(row[9]) if len(row) > 9 else '',
            "funcionarios": {},
        }

    # ========================
    # 3. LER BENEFICIARIO
    # ========================
    ws_ben = wb['Beneficiario']

    MAP_BEN = {
        'cpf': 0,
        'codigo_local': 1,
        'centro_custo': 2,
        'matricula': 3,
        'nome_completo': 4,
        'nome_impressao': 5,
        'data_nascimento': 6,
        'sexo': 7,
        'faixa_salarial': 8,
    }

    # Encontrar colunas de produto na linha 2
    # Headers podem ter newlines ou estarem colados com "Valor do crédito"
    col_produtos = {}
    ben_iter = iter(ws_ben.iter_rows(min_row=2, values_only=True))
    header_row = next(ben_iter, None)
    if header_row:
        for col_idx, val in enumerate(header_row, start=1):
            if val is None:
                continue
            h = _safe_str(val).strip()
            h = h.split('\n')[0].strip()
            if not h:
                continue
            if h in COLUNAS_PRODUTO:
                col_produtos[col_idx] = h
            else:
                for nome, codigo in COLUNAS_PRODUTO.items():
                    if h.startswith(nome) or nome.startswith(h):
                        col_produtos[col_idx] = nome
                        break

    for row_num, row in enumerate(ben_iter, start=3):
        if not row:
            continue
        cpf_raw = _safe_str(row[0] if len(row) > 0 else '')
        codigo_local = _safe_str(row[1] if len(row) > 1 else '')
        matricula = _safe_str(row[3] if len(row) > 3 else '')
        nome = _safe_str(row[4] if len(row) > 4 else '')
        data_nasc_raw = row[6] if len(row) > 6 else None

        if not cpf_raw and not nome:
            continue

        erros_linha_atual = []

        # 1. Validar CPF
        cpf = ""
        if not cpf_raw:
            erros_linha_atual.append("CPF do beneficiário ausente")
        else:
            cpf = re.sub(r'\D', '', cpf_raw)
            if len(cpf) < 11:
                cpf = cpf.zfill(11)
            if len(cpf) != 11:
                erros_linha_atual.append(f"CPF inválido (tamanho incorreto: {len(cpf)} dígitos)")

        # 2. Validar Nome
        if not nome:
            erros_linha_atual.append("Nome do beneficiário ausente")

        # 3. Validar Código Local de Entrega
        if not codigo_local:
            erros_linha_atual.append("Código local de entrega (CNPJ) ausente")

        # 4. Validar Matrícula
        if not matricula:
            erros_linha_atual.append("Matrícula ausente")

        # 5. Validar Data de Nascimento
        data_nasc = _parse_date(data_nasc_raw)
        if not data_nasc:
            erros_linha_atual.append("Data de nascimento ausente ou inválida")

        # 6. Validar se há pelo menos um benefício/produto com valor > 0
        tem_beneficio = False
        for col_idx, nome_produto in col_produtos.items():
            raw_val = row[col_idx - 1] if len(row) > col_idx - 1 else None
            if raw_val is not None:
                try:
                    valor = Decimal(str(raw_val).replace(',', '.'))
                    if valor > 0:
                        tem_beneficio = True
                        break
                except:
                    pass

        if not tem_beneficio:
            erros_linha_atual.append("Nenhum benefício preenchido com valor maior que zero")

        if erros_linha_atual:
            result['linhas_com_erro'].append({
                "tipo_erro": "INFORMACAO_AUSENTE",
                "linha": row_num,
                "dados": {
                    "cpf": cpf_raw,
                    "nome": nome,
                    "codigo_local": codigo_local,
                    "matricula": matricula,
                    "data_nascimento": _safe_str(data_nasc_raw),
                },
                "erros": erros_linha_atual
            })
        else:
            if codigo_local not in locais:
                locais[codigo_local] = {
                    "nome": f"{matricula}",
                    "cnpj": codigo_local,
                    "valor_condo": Decimal('0.00'),
                    "rua": '',
                    "numero": '',
                    "complemento": '',
                    "bairro": '',
                    "cidade": '',
                    "estado": '',
                    "cep": '',
                    "funcionarios": {},
                    "nao_cadastrado_local_entrega": True,
                }

            func_key = f"{codigo_local}_{cpf}"
            if func_key not in locais[codigo_local]["funcionarios"]:
                locais[codigo_local]["funcionarios"][func_key] = {
                    "nome": nome.upper() if nome else '',
                    "cpf": cpf,
                    "matricula": matricula,
                    "departamento": '',
                    "funcao": '',
                    "data_nascimento": data_nasc,
                    "cep": None,
                    "endereco_rua": None,
                    "endereco_numero": None,
                    "endereco_complemento": None,
                    "endereco_bairro": None,
                    "valor_bene": Decimal('0.00'),
                    "movimentacoes": [],
                }

            func = locais[codigo_local]["funcionarios"][func_key]

            for col_idx, nome_produto in col_produtos.items():
                raw_val = row[col_idx - 1] if len(row) > col_idx - 1 else None
                if raw_val is None:
                    continue
                try:
                    valor = Decimal(str(raw_val).replace(',', '.'))
                except:
                    continue
                if valor == 0:
                    continue

                func["movimentacoes"].append({
                    "produto": nome_produto,
                    "codigo_produto": COLUNAS_PRODUTO.get(nome_produto, ''),
                    "valor": valor,
                })
                func["valor_bene"] += valor
                locais[codigo_local]["valor_condo"] += valor
                result['summary']['valor_total_beneficios'] += valor

    wb.close()

    # ========================
    # 4. MONTAR CONDOMINIOS
    # ========================
    erros_condominios = []
    for codigo, local in locais.items():
        lista_func = []
        for fkey, func in local["funcionarios"].items():
            if not func["movimentacoes"]:
                continue
            lista_func.append({
                "nome": func["nome"],
                "cpf": func["cpf"],
                "matricula": func["matricula"],
                "departamento": func["departamento"],
                "funcao": func["funcao"],
                "data_nascimento": func["data_nascimento"],
                "cep": func["cep"],
                "endereco_rua": func["endereco_rua"],
                "endereco_numero": func["endereco_numero"],
                "endereco_complemento": func["endereco_complemento"],
                "endereco_bairro": func["endereco_bairro"],
                "valor_bene": func["valor_bene"],
                "movimentacoes": func["movimentacoes"],
            })

        if lista_func:
            missing_infos = []
            if local.get("nao_cadastrado_local_entrega"):
                missing_infos.append("Não cadastrado na aba 'Local de Entrega'")
            else:
                if not local.get("nome") or local["nome"].startswith("Local: "):
                    missing_infos.append("Nome do condomínio ausente ou inválido")
                if not local.get("cnpj"):
                    missing_infos.append("CNPJ do condomínio ausente")
                if not local.get("estado"):
                    missing_infos.append("Estado ausente")
                if not local.get("cep"):
                    missing_infos.append("CEP ausente")

            if missing_infos:
                erros_condominios.append({
                    "cnpj": local["cnpj"],
                    "nome": local["nome"],
                    "erros": missing_infos
                })

            result["condominios"].append({
                "nome": local["nome"],
                "cnpj": local["cnpj"],
                "valor_condo": local["valor_condo"],
                "rua": local.get("rua"),
                "numero": local.get("numero"),
                "complemento": local.get("complemento"),
                "bairro": local.get("bairro"),
                "cidade": local.get("cidade"),
                "estado": local.get("estado"),
                "cep": local.get("cep"),
                "funcionarios": lista_func,
            })
            result['summary']['total_funcionarios'] += len(lista_func)
            result['summary']['total_movimentacoes'] += sum(len(f["movimentacoes"]) for f in lista_func)

    result["erros_condominios"] = erros_condominios
    result['summary']['total_condominios'] = len(result["condominios"])
    if result["condominios"]:
        result['summary']['primeiro_cnpj_processado'] = result["condominios"][0].get("cnpj", "N/A")

    # Se há erros acumulados (linhas com erro ou erros de condomínio), retornamos o payload focado nos erros
    if result["linhas_com_erro"] or result["erros_condominios"]:
        return {
            "file_upload_id": file_upload_id,
            "status": "ERRO",
            "condominios": [],
            "errors": ["Planilha contém informações obrigatórias ausentes ou incorretas."],
            "linhas_com_erro": result["linhas_com_erro"],
            "erros_condominios": result["erros_condominios"],
            "summary": {
                "total_condominios": 0,
                "total_funcionarios": 0,
                "total_movimentacoes": 0,
                "valor_total_beneficios": Decimal('0.00'),
                "data_competencia_arquivo": result['summary']['data_competencia_arquivo'],
                "primeiro_cnpj_processado": "N/A",
            }
        }

    return result


def test_parse():
    import json
    import os
    from decimal import Decimal

    file_path = os.path.join(os.path.dirname(__file__), 'VR-exemplo.xlsm')
    if not os.path.exists(file_path):
        file_path = os.path.join(os.path.dirname(__file__), 'Template_VR.xlsm')
    if not os.path.exists(file_path):
        print(f"ERRO: Arquivo não encontrado")
        return

    data = parse_fut_template(file_path, file_upload_id=999, valor_max_beneficio=Decimal('9999.99'))

    # resumo
    s = data['summary']
    print(f"Total condominios: {s['total_condominios']}")
    print(f"Total funcionarios: {s['total_funcionarios']}")
    print(f"Total movimentacoes: {s['total_movimentacoes']}")
    print(f"Valor total beneficios: {s['valor_total_beneficios']}")
    print(f"Data competencia arquivo: {s['data_competencia_arquivo']}")
    print(f"Erros: {len(data['errors'])}")
    print(f"Linhas com erro: {len(data['linhas_com_erro'])}")
    print()

    for c in data['condominios']:
        print(f"Condominio: {c['nome']} (CNPJ: {c['cnpj']})")
        print(f"  Endereco: {c['rua']}, {c['numero']} - {c['bairro']}, {c['cidade']}/{c['estado']} CEP:{c['cep']}")
        print(f"  Funcionarios: {len(c['funcionarios'])}")
        for f in c['funcionarios']:
            print(f"    - {f['nome']} | CPF: {f['cpf']} | Nasc: {f['data_nascimento']} | Mat: {f['matricula']}")
            for m in f['movimentacoes']:
                print(f"        > {m['produto']}: R$ {m['valor']}")
        print()

    print("=== JSON completo ===")
    safe = json.dumps(data, default=str, indent=2, ensure_ascii=False)
    print(safe)


if __name__ == '__main__':
    test_parse()
