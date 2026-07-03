import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
import openpyxl
import logging

# Tentar importar o modelo Condominio para buscar nomes no banco
try:
    from entidades.models import Condominio
    HAS_DB = True
except ImportError:
    HAS_DB = False
    Condominio = None

logger = logging.getLogger(__name__)

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


def _buscar_nome_condominio(cnpj):
    """
    Busca o nome do condomínio no banco de dados pelo CNPJ.
    Retorna o nome ou None se não encontrado.
    """
    if not HAS_DB or not Condominio:
        return None
    
    try:
        cnpj_limpo = re.sub(r'\D', '', str(cnpj))
        if not cnpj_limpo or len(cnpj_limpo) < 14:
            return None
            
        condominio = Condominio.objects.filter(cnpj=cnpj_limpo).first()
        if condominio and condominio.nome:
            return condominio.nome
    except Exception as e:
        logger.warning(f"Erro ao buscar condomínio por CNPJ {cnpj}: {e}")
    
    return None


def _buscar_dados_condominio(cnpj):
    """
    Busca todos os dados do condomínio no banco de dados pelo CNPJ.
    Retorna um dicionário com os dados ou None se não encontrado.
    """
    if not HAS_DB or not Condominio:
        return None
    
    try:
        cnpj_limpo = re.sub(r'\D', '', str(cnpj))
        if not cnpj_limpo or len(cnpj_limpo) < 14:
            return None
            
        condominio = Condominio.objects.filter(cnpj=cnpj_limpo).first()
        if condominio:
            return {
                "nome": condominio.nome or '',
                "rua": condominio.endereco or '',
                "numero": condominio.numero or '',
                "complemento": condominio.complemento or '',
                "bairro": condominio.bairro or '',
                "cidade": condominio.cidade or '',
                "estado": condominio.estado or '',
                "cep": condominio.cep or '',
            }
    except Exception as e:
        logger.warning(f"Erro ao buscar dados do condomínio por CNPJ {cnpj}: {e}")
    
    return None


def parse_fut_template(file_path, file_upload_id, valor_max_beneficio=None):
    """
    Parse do template FUT (VR) - planilha .xlsm com abas:
    - Sumario: dados gerais e competência
    - Local de Entrega: dados dos condomínios
    - Beneficiario: dados dos funcionários e movimentações
    """
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
        wb = openpyxl.load_workbook(file_path, data_only=True, keep_vba=False)
    except Exception as e:
        result['errors'].append(f"Erro ao abrir planilha: {str(e)}")
        return result

    # ========================
    # 1. LER SUMARIO
    # ========================
    try:
        ws_sum = wb['Sumario']
        data_disponivel = _safe_str(ws_sum['O6'].value or ws_sum['C6'].value or '')
        result['summary']['data_competencia_arquivo'] = _parse_date(data_disponivel)
    except Exception as e:
        logger.warning(f"Erro ao ler Sumario: {e}")
        result['errors'].append(f"Erro ao ler aba Sumario: {str(e)}")

    # ========================
    # 2. LER LOCAIS DE ENTREGA (condominios)
    # ========================
    locais = {}  # codigo_local -> dados
    
    try:
        ws_locais = wb['Local de Entrega']
        
        for row in ws_locais.iter_rows(min_row=2, values_only=True):
            codigo = _safe_str(row[0])
            if not codigo:
                continue

            # Limpar CNPJ (remover pontuação)
            codigo_limpo = re.sub(r'\D', '', codigo)
            if not codigo_limpo:
                continue

            # Tentar buscar nome do local
            nome_local = _safe_str(row[1]) if len(row) > 1 and row[1] else None
            
            # Se não veio nome ou veio só o código, buscar no banco
            if not nome_local or nome_local == codigo or nome_local == codigo_limpo:
                nome_bd = _buscar_nome_condominio(codigo_limpo)
                if nome_bd:
                    nome_local = nome_bd
                else:
                    # Usar o nome da planilha se disponível
                    nome_local = _safe_str(row[1]) if len(row) > 1 and row[1] else f"Condomínio {codigo_limpo}"

            # Buscar dados atualizados do banco
            dados_bd = _buscar_dados_condominio(codigo_limpo)
            
            locais[codigo_limpo] = {
                "nome": nome_local,
                "cnpj": codigo_limpo,
                "valor_condo": Decimal('0.00'),
                "rua": dados_bd.get('rua') if dados_bd else (_safe_str(row[3]) if len(row) > 3 else ''),
                "numero": dados_bd.get('numero') if dados_bd else (_safe_str(row[4]) if len(row) > 4 else ''),
                "complemento": dados_bd.get('complemento') if dados_bd else (_safe_str(row[5]) if len(row) > 5 else ''),
                "bairro": dados_bd.get('bairro') if dados_bd else (_safe_str(row[6]) if len(row) > 6 else ''),
                "cidade": dados_bd.get('cidade') if dados_bd else (_safe_str(row[7]) if len(row) > 7 else ''),
                "estado": dados_bd.get('estado') if dados_bd else (_safe_str(row[8]) if len(row) > 8 else ''),
                "cep": dados_bd.get('cep') if dados_bd else (_safe_str(row[9]) if len(row) > 9 else ''),
                "funcionarios": {},
                "from_db": dados_bd is not None,
            }
            
    except Exception as e:
        logger.warning(f"Erro ao ler Local de Entrega: {e}")
        result['errors'].append(f"Erro ao ler aba Local de Entrega: {str(e)}")

    # ========================
    # 3. LER BENEFICIARIO
    # ========================
    try:
        ws_ben = wb['Beneficiario']
        max_row = ws_ben.max_row

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
        for col_idx in range(1, ws_ben.max_column + 1):
            val = ws_ben.cell(row=2, column=col_idx).value
            if val:
                h = _safe_str(val).strip()
                h = h.split('\n')[0].strip()
                # Tenta match exato primeiro, depois prefixo
                if h in COLUNAS_PRODUTO:
                    col_produtos[col_idx] = h
                else:
                    for nome, codigo in COLUNAS_PRODUTO.items():
                        if h.startswith(nome) or nome.startswith(h):
                            col_produtos[col_idx] = nome
                            break

    for row_idx in range(3, max_row + 1):
        cpf_raw = _safe_str(ws_ben.cell(row=row_idx, column=MAP_BEN['cpf'] + 1).value)
        codigo_local = _safe_str(ws_ben.cell(row=row_idx, column=MAP_BEN['codigo_local'] + 1).value)
        matricula = _safe_str(ws_ben.cell(row=row_idx, column=MAP_BEN['matricula'] + 1).value)
        nome = _safe_str(ws_ben.cell(row=row_idx, column=MAP_BEN['nome_completo'] + 1).value)
        data_nasc_raw = ws_ben.cell(row=row_idx, column=MAP_BEN['data_nascimento'] + 1).value
        line_num = row_idx + 1
        if not cpf_raw and not nome:
            continue
        for row_idx in range(3, max_row + 1):
            cpf_raw = _safe_str(ws_ben.cell(row=row_idx, column=MAP_BEN['cpf'] + 1).value)
            codigo_local = _safe_str(ws_ben.cell(row=row_idx, column=MAP_BEN['codigo_local'] + 1).value)
            matricula = _safe_str(ws_ben.cell(row=row_idx, column=MAP_BEN['matricula'] + 1).value)
            nome = _safe_str(ws_ben.cell(row=row_idx, column=MAP_BEN['nome_completo'] + 1).value)
            data_nasc_raw = ws_ben.cell(row=row_idx, column=MAP_BEN['data_nascimento'] + 1).value
            line_num = row_idx + 1

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
            raw_val = ws_ben.cell(row=row_idx, column=col_idx).value
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
                "linha": line_num,
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
            if not cpf_raw:
                result['linhas_com_erro'].append({
                    "tipo_erro": "CPF_AUSENTE",
                    "linha": line_num,
                    "dados": {"nome": nome, "codigo_local": codigo_local}
                })
                continue

            cpf = re.sub(r'\D', '', cpf_raw)
            if len(cpf) < 11:
                cpf = cpf.zfill(11)

            if not codigo_local:
                result['linhas_com_erro'].append({
                    "tipo_erro": "LOCAL_ENTREGA_AUSENTE",
                    "linha": line_num,
                    "dados": {"cpf": cpf, "nome": nome}
                })
                continue

            # Limpar código local
            codigo_limpo = re.sub(r'\D', '', codigo_local)
            if not codigo_limpo:
                result['linhas_com_erro'].append({
                    "tipo_erro": "LOCAL_ENTREGA_INVALIDO",
                    "linha": line_num,
                    "dados": {"cpf": cpf, "nome": nome, "codigo_local": codigo_local}
                })
                continue

            # Se o local não existe no dicionário, criar
            if codigo_limpo not in locais:
                # Tentar buscar nome no banco
                nome_bd = _buscar_nome_condominio(codigo_limpo)
                dados_bd = _buscar_dados_condominio(codigo_limpo)
                
                nome_local = nome_bd if nome_bd else f"Condomínio {codigo_limpo}"
                
                locais[codigo_limpo] = {
                    "nome": nome_local,
                    "cnpj": codigo_limpo,
                    "valor_condo": Decimal('0.00'),
                    "rua": dados_bd.get('rua') if dados_bd else '',
                    "numero": dados_bd.get('numero') if dados_bd else '',
                    "complemento": dados_bd.get('complemento') if dados_bd else '',
                    "bairro": dados_bd.get('bairro') if dados_bd else '',
                    "cidade": dados_bd.get('cidade') if dados_bd else '',
                    "estado": dados_bd.get('estado') if dados_bd else '',
                    "cep": dados_bd.get('cep') if dados_bd else '',
                    "funcionarios": {},
                    "from_db": dados_bd is not None,
                }
                
                result['linhas_com_erro'].append({
                    "tipo_erro": "LOCAL_NAO_CADASTRADO",
                    "linha": line_num,
                    "dados": {
                        "codigo_local": codigo_limpo,
                        "cpf": cpf,
                        "nome": nome_local,
                        "criado_automaticamente": True
                    }
                })

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
            data_nasc = _parse_date(data_nasc_raw)

            func_key = f"{codigo_limpo}_{cpf}"
            if func_key not in locais[codigo_limpo]["funcionarios"]:
                locais[codigo_limpo]["funcionarios"][func_key] = {
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
            func = locais[codigo_limpo]["funcionarios"][func_key]

            for col_idx, nome_produto in col_produtos.items():
                raw_val = ws_ben.cell(row=row_idx, column=col_idx).value
                if raw_val is None:
                    continue
                try:
                    valor = Decimal(str(raw_val).replace(',', '.'))
                except:
                    continue
                if valor == 0:
                    continue
            for col_idx, nome_produto in col_produtos.items():
                raw_val = ws_ben.cell(row=row_idx, column=col_idx).value
                if raw_val is None:
                    continue
                try:
                    if isinstance(raw_val, (int, float)):
                        valor = Decimal(str(raw_val))
                    else:
                        valor = Decimal(str(raw_val).replace(',', '.'))
                except (InvalidOperation, ValueError):
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
                # Verificar valor máximo
                if valor > valor_max_beneficio:
                    result['linhas_com_erro'].append({
                        "tipo_erro": "VALOR_EXCEDE_LIMITE",
                        "linha": line_num,
                        "dados": {
                            "cpf": cpf,
                            "produto": nome_produto,
                            "valor": float(valor),
                            "limite": float(valor_max_beneficio)
                        }
                    })
                    valor = valor_max_beneficio

                func["movimentacoes"].append({
                    "produto": nome_produto,
                    "codigo_produto": COLUNAS_PRODUTO.get(nome_produto, ''),
                    "valor": valor,
                })
                func["valor_bene"] += valor
                locais[codigo_limpo]["valor_condo"] += valor
                result['summary']['valor_total_beneficios'] += valor

    except Exception as e:
        logger.error(f"Erro ao ler Beneficiario: {e}")
        result['errors'].append(f"Erro ao ler aba Beneficiario: {str(e)}")

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

    # Log de warnings
    if result['linhas_com_erro']:
        logger.warning(f"Parser encontrou {len(result['linhas_com_erro'])} linhas com erro")
        for erro in result['linhas_com_erro']:
            logger.warning(f"  - {erro.get('tipo_erro')}: {erro.get('dados')}")

    return result


def test_parse():
    """Função de teste para verificar o parser"""
    import json
    import os
    from decimal import Decimal

    # Tentar diferentes caminhos de arquivo
    file_paths = [
        os.path.join(os.path.dirname(__file__), 'VR-exemplo.xlsm'),
        os.path.join(os.path.dirname(__file__), 'Template_VR.xlsm'),
        os.path.join(os.path.dirname(__file__), 'VR.xlsm'),
    ]
    
    file_path = None
    for path in file_paths:
        if os.path.exists(path):
            file_path = path
            break
    
    if not file_path:
        print(f"ERRO: Nenhum arquivo encontrado em: {file_paths}")
        return

    print(f"📂 Processando: {file_path}")
    data = parse_fut_template(file_path, file_upload_id=999, valor_max_beneficio=Decimal('9999.99'))

    # Resumo
    s = data['summary']
    print(f"\n📊 RESUMO:")
    print(f"  Total condominios: {s['total_condominios']}")
    print(f"  Total funcionarios: {s['total_funcionarios']}")
    print(f"  Total movimentacoes: {s['total_movimentacoes']}")
    print(f"  Valor total beneficios: R$ {s['valor_total_beneficios']:,.2f}")
    print(f"  Data competencia arquivo: {s['data_competencia_arquivo']}")
    print(f"  Primeiro CNPJ: {s['primeiro_cnpj_processado']}")
    print(f"  Erros: {len(data['errors'])}")
    print(f"  Linhas com erro: {len(data['linhas_com_erro'])}")
    
    # Detalhes dos condomínios
    print(f"\n🏢 CONDOMÍNIOS ({len(data['condominios'])}):")
    for i, c in enumerate(data['condominios'][:5], 1):
        print(f"\n  {i}. {c['nome']} (CNPJ: {c['cnpj']})")
        print(f"     Endereco: {c['rua']}, {c['numero']} - {c['bairro']}, {c['cidade']}/{c['estado']} CEP:{c['cep']}")
        print(f"     Funcionarios: {len(c['funcionarios'])}")
        print(f"     Valor total: R$ {c['valor_condo']:,.2f}")
        if c.get('from_db'):
            print("     ✅ Dados atualizados do banco")
    
    if len(data['condominios']) > 5:
        print(f"\n  ... e mais {len(data['condominios']) - 5} condomínios")
    
    # Erros
    if data['linhas_com_erro']:
        print(f"\n⚠️ ERROS ENCONTRADOS ({len(data['linhas_com_erro'])}):")
        for erro in data['linhas_com_erro'][:10]:
            print(f"  - {erro.get('tipo_erro')}: {erro.get('dados')}")
        if len(data['linhas_com_erro']) > 10:
            print(f"  ... e mais {len(data['linhas_com_erro']) - 10} erros")

    # JSON completo (opcional)
    print("\n📄 JSON completo:")
    safe = json.dumps(data, default=str, indent=2, ensure_ascii=False)
    print(safe[:2000] + "..." if len(safe) > 2000 else safe)


if __name__ == '__main__':
    test_parse()