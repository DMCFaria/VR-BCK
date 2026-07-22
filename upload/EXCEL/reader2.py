import os
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
import openpyxl


CODIGO_PRODUTO_PADRAO = '207'

# Mapeamento dos headers de produto encontrados nas planilhas para o
# código do produto usado nos registros 50/60 do TXT de compra.
COLUNAS_PRODUTO = {
    # ===== Sem prefixo "VR " (VR-exemplo.xlsm / Template_VR_OLD.xlsx) =====
    'Refeição': CODIGO_PRODUTO_PADRAO,
    'Multi Refeição': CODIGO_PRODUTO_PADRAO,
    'Alimentação': '27',
    'Multi Alimentação': '27',
    'Auto': '28',
    'Mobilidade': '28',
    'VR Mobilidade': '28',
    'Multi Mobilidade': '28',
    'VR Multi Mobilidade': '28',
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
    'Multi - Home Office': CODIGO_PRODUTO_PADRAO,
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
    'VR Multi - Home Office': CODIGO_PRODUTO_PADRAO,
}

# Mapeamento dos headers de produto para o TIPO normalizado.
# Esse tipo é o valor que deve aparecer em todos os documentos exportados.
MAPEAMENTO_PRODUTO_TIPO = {
    'Refeição': 'Refeição',
    'Multi Refeição': 'Multi - Refeição',
    'Alimentação': 'Alimentação',
    'Multi Alimentação': 'Multi - Alimentação',
    'Auto': 'Auto',
    'Mobilidade': 'Multi - Mobilidade',
    'VR Mobilidade': 'Multi - Mobilidade',
    'Multi Mobilidade': 'Multi - Mobilidade',
    'VR Multi Mobilidade': 'Multi - Mobilidade',
    'Cesta': 'Boas Festas',
    'Boas Festas': 'Boas Festas',
    'Auxílio Alimentação': 'Alimentação',
    'Multi Auxílio Alimentação': 'Multi - Alimentação',
    'Auxílio Refeição': 'Refeição',
    'Multi Auxílio Refeição': 'Multi - Refeição',
    'Multibenefício': 'Multi - VR+VA',
    'Multibenefícios': 'Multi - VR+VA',
    'Auxílio VR+VA': 'Multi - VR+VA',
    'Multi Auxílio VR+VA': 'Multi - VR+VA',
    'Multi Premiação': 'Multi - Home Office',
    'Multi - Home Office': 'Multi - Home Office',
    'VR Refeição': 'Refeição',
    'VR Alimentação': 'Alimentação',
    'VR Auto': 'Auto',
    'VR Alimentação Cesta': 'Boas Festas',
    'VR Boas Festas': 'Boas Festas',
    'VR Auxílio Alimentação': 'Alimentação',
    'VR Auxílio Refeição': 'Refeição',
    'VR Multibenefícios': 'Multi - VR+VA',
    'VR+VA': 'Multi - VR+VA',
    'VR Multi Refeição': 'Multi - Refeição',
    'VR Multi Alimentação': 'Multi - Alimentação',
    'VR Multi Alimentação Valor do crédito': 'Multi - Alimentação',
    'VR Multi Refeição Auxílio': 'Multi - Refeição',
    'VR Multi Alimentação Auxílio': 'Multi - Alimentação',
    'VR Multi VR+VA': 'Multi - VR+VA',
    'VR Multi - Home Office': 'Multi - Home Office',
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


def _normalizar_cnpj(val):
    """Remove tudo que não for dígito e preenche com zeros à esquerda até 14."""
    if val is None:
        return ''
    return re.sub(r'\D', '', str(val)).zfill(14)[:14]


def parse_fut_template(file_path, file_upload_id, valor_max_beneficio=None, administradora_cnpj=None):
    if valor_max_beneficio is None:
        valor_max_beneficio = Decimal('9999.99')

    result = {
        "file_upload_id": file_upload_id,
        "cartao_admin": None,
        "administradora_cnpj": None,
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

    file_ext = os.path.splitext(file_path)[1].lower()

    if file_ext in ('.csv', '.xls'):
        result['errors'].append(
            f"Formato '{file_ext}' não suportado. Use arquivos .xlsx ou .xlsm no layout VR."
        )
        return result

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
    except Exception as e:
        result['errors'].append(f"Erro ao abrir planilha: {str(e)}")
        return result

    # ========================
    # 1. LER SUMARIO
    # ========================
    ws_sum = wb['Sumario']
    data_disponivel = ''
    cnpj_sumario = ''
    for row in ws_sum.iter_rows(min_row=1, max_row=6, values_only=True):
        if not row:
            continue
        primeiro_valor = _safe_str(row[0] if len(row) > 0 else '')
        if 'CNPJ' in primeiro_valor.upper() or 'CÓDIGO DO CLIENTE' in primeiro_valor.upper():
            for cell in row[1:]:
                val = _safe_str(cell)
                if val:
                    cnpj_sumario = _normalizar_cnpj(val)
                    if cnpj_sumario:
                        break
            continue
        # data disponível costuma estar na linha 6
        for cell in row:
            val = _safe_str(cell)
            if val:
                parsed = _parse_date(val)
                if parsed:
                    data_disponivel = val
                    break

    result['summary']['data_competencia_arquivo'] = _parse_date(data_disponivel)

    admin_cnpj_normalizado = _normalizar_cnpj(administradora_cnpj or cnpj_sumario)
    result['administradora_cnpj'] = admin_cnpj_normalizado

    # ========================
    # 2. LER LOCAIS DE ENTREGA (condominios)
    # ========================
    ws_locais = wb['Local de Entrega']
    locais = {}  # codigo_local -> dados
    locais_raw = []  # lista de codigos na ordem da planilha

    for row in ws_locais.iter_rows(min_row=2, values_only=True):
        codigo = _safe_str(row[0])
        if not codigo:
            continue

        locais_raw.append(codigo)
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

    # Determina se é modo "cartão admin" baseado apenas na aba Local de Entrega.
    # Regra acordada: se houver apenas 1 local de entrega => cartao_admin=True
    # (a administradora centraliza a entrega). Se houver 0 locais => erro.
    # Se houver >1 local => condomínios normais, cartao_admin=False.
    cartao_admin = False
    if not locais_raw:
        result['errors'].append(
            "Aba 'Local de Entrega' não contém nenhum local de entrega cadastrado."
        )
    elif len(locais_raw) == 1:
        cartao_admin = True
    else:
        cartao_admin = False

    result['cartao_admin'] = cartao_admin

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

    # Encontrar colunas de produto
    # Headers podem estar na linha 1, 2 ou 3 dependendo do template
    # Headers podem ter newlines ou estarem colados com "Valor do crédito"
    col_produtos = {}
    ben_rows = list(ws_ben.iter_rows(min_row=1, max_row=5, values_only=True))

    def _match_produto_header(val):
        """Retorna o nome do produto se o valor for um header conhecido."""
        if val is None:
            return None
        h = _safe_str(val).strip().split('\n')[0].strip()
        if not h:
            return None
        if h in COLUNAS_PRODUTO:
            return h
        # Match parcial: o header deve conter o nome do produto como palavra/frase
        # (evita que "VR Multi" casse com "VR Multi Mobilidade").
        h_lower = h.lower()
        for nome in COLUNAS_PRODUTO:
            if nome.lower() in h_lower:
                return nome
        return None

    # Escolhe a linha com maior número de headers de produto reconhecidos.
    best_row = None
    best_row_num = 2
    best_count = 0
    for try_idx, try_row in enumerate(ben_rows):
        if not try_row:
            continue
        matches = [_match_produto_header(v) for v in try_row]
        count = sum(1 for m in matches if m)
        # Só considera se tiver pelo menos 2 produtos (evita falsos positivos)
        if count >= 2 and count > best_count:
            best_row = try_row
            best_row_num = try_idx + 1
            best_count = count

    if not best_row and ben_rows:
        # Fallback: usa a primeira linha que tiver algum match
        for try_idx, try_row in enumerate(ben_rows):
            if any(_match_produto_header(v) for v in try_row):
                best_row = try_row
                best_row_num = try_idx + 1
                break
        if not best_row:
            best_row = ben_rows[1] if len(ben_rows) > 1 else ben_rows[0]
            best_row_num = 2

    header_row = best_row
    header_row_num = best_row_num

    if header_row:
        for col_idx, val in enumerate(header_row, start=1):
            produto = _match_produto_header(val)
            if produto:
                col_produtos[col_idx] = produto

    data_start_row = header_row_num + 1

    data_rows = list(ws_ben.iter_rows(min_row=data_start_row, values_only=True))
    for row_num, row in enumerate(data_rows, start=data_start_row):
        if not row:
            continue

        # Pular linhas completamente vazias (memória do Excel)
        if all(v is None or str(v).strip() == '' for v in row):
            continue

        cpf_raw = _safe_str(row[0] if len(row) > 0 else '')
        codigo_local = _safe_str(row[1] if len(row) > 1 else '')
        matricula = _safe_str(row[3] if len(row) > 3 else '')
        nome = _safe_str(row[4] if len(row) > 4 else '')
        data_nasc_raw = row[6] if len(row) > 6 else None

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
                # No modo cartão admin os condomínios vêm apenas da aba Beneficiário.
                # A coluna "Matrícula" costuma trazer o nome descritivo do condomínio,
                # então usamos ela como nome quando disponível.
                nome_local = matricula.strip() if matricula and str(matricula).strip() else codigo_local
                locais[codigo_local] = {
                    "nome": nome_local,
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
                    "tipo": MAPEAMENTO_PRODUTO_TIPO.get(nome_produto, nome_produto),
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
            if not cartao_admin and local.get("nao_cadastrado_local_entrega"):
                # No modo normal (condomínios) exigimos que o local esteja na aba Local de Entrega
                missing_infos.append("Não cadastrado na aba 'Local de Entrega'")
            else:
                if not local.get("nome") or local["nome"].startswith("Local: "):
                    missing_infos.append("Nome do condomínio ausente ou inválido")
                if not local.get("cnpj"):
                    missing_infos.append("CNPJ do condomínio ausente")
                # No modo cartão admin o endereço será pesquisado automaticamente;
                # ainda assim, se a planilha trouxer endereço, usamos ela como fonte fiel.
                if not cartao_admin:
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

    # Se há erros acumulados (erros gerais, linhas com erro ou erros de condomínio),
    # retornamos o payload focado nos erros.
    if result["errors"] or result["linhas_com_erro"] or result["erros_condominios"]:
        mensagem_erro = "Planilha contém informações obrigatórias ausentes ou incorretas."
        if result["errors"]:
            mensagem_erro = "; ".join(result["errors"])
        return {
            "file_upload_id": file_upload_id,
            "cartao_admin": result["cartao_admin"],
            "administradora_cnpj": result["administradora_cnpj"],
            "status": "ERRO",
            "condominios": [],
            "errors": [mensagem_erro],
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

    data = parse_fut_template(
        file_path,
        file_upload_id=999,
        valor_max_beneficio=Decimal('9999.99'),
        administradora_cnpj='35315360000167',
    )

    # resumo
    s = data['summary']
    print(f"cartao_admin: {data.get('cartao_admin')}")
    print(f"administradora_cnpj: {data.get('administradora_cnpj')}")
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
