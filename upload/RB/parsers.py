import re
import os
from decimal import Decimal, InvalidOperation
from datetime import datetime



# --- SUAS CONSTANTES DE MAPEAMENTO ---
COL_SEQUENCIAL = slice(0, 5)
COL_TIPO_REGISTRO_WIDER = slice(5,6) # Contém o tipo (ex: "3 ", "4 ")
COL_CNPJ = slice(6, 19)

# Tipo 1: CONDOMÍNIO
COL_CONDOMINIO_RAZAO_SOCIAL = slice(20, 60)

# Tipo 3: FUNCIONÁRIO
COL_FUNCIONARIO_MATRICULA = slice(19, 32)
COL_FUNCIONARIO_NOME = slice(32, 80)
COL_FUNCIONARIO_CPF = slice(183, 194)

# Tipo 4: BENEFÍCIO
COL_BENEFICIO_MATRICULA = slice(19, 32)
COL_BENEFICIO_NUM_DIAS = slice(104, 108)
COL_BENEFICIO_VALOR = slice(108, 116)

# --- FUNÇÕES DE LIMPEZA ---

def format_valor_rb(text):
    """Garante que '000110000' vire Decimal('1100.00')"""
    if not text: return Decimal('0.00')
    digits = re.sub(r'\D', '', text.strip())
    if not digits: return Decimal('0.00')
    try:
        return Decimal(digits) / Decimal('100.00')
    except:
        return Decimal('0.00')

def extrair_cpf_estrito(line):
    """Pega o CPF na posição 183-195 ou recusa se inválido."""
    raw = re.sub(r'\D', '', line[COL_FUNCIONARIO_CPF].strip())

    # Se falhar a posição fixa, busca dinâmica
    if not raw:
        match = re.search(r'(\d{11,12})', line)
        raw = match.group(1) if match else ""

    # 2. Tratativa de 12 dígitos (RB/Ticket)
    # Se vier com 12, tentamos validar os 11 primeiros
    if len(raw) == 12:
        cpf_candidato = raw[:11]
    elif len(raw) == 11:
        cpf_candidato = raw
    else:
        return None

    # 3. VALIDAÇÃO MATEMÁTICA
    if cpf_valido_matematicamente(cpf_candidato):
        return cpf_candidato

    # Se o CPF de 12 dígitos da RB falhou pegando os 11 primeiros, 
    # pode ser que o dígito extra estivesse no INÍCIO (raro, mas possível).
    # Tentamos validar os últimos 11 apenas por desencargo:
    if len(raw) == 12:
        cpf_candidato_v2 = raw[1:]
        if cpf_valido_matematicamente(cpf_candidato_v2):
            return cpf_candidato_v2

    return None

# --- PARSER ---

def parse_rb_layout(file_path, file_upload_id):
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

    if not os.path.exists(file_path):
        result['errors'].append("Arquivo não encontrado.")
        return result

    try:
        funcs_cache = {} 
        cnpjs_vistos = []
        cpfs_vistos = set()
        current_cnpj = None

        with open(file_path, 'r', encoding='latin-1') as f:
            for i, line in enumerate(f):
                if len(line.strip()) < 10: continue
                line_num = i + 1
                
                # O tipo está na posição 5, mas sua constante pega 5:7
                tipo = line[COL_TIPO_REGISTRO_WIDER].strip()
                # TIPO 0: HEADER
                if tipo == '0':
                    match = re.search(r'(\d{8})', line)
                    if match:
                        d = match.group(1)
                        # Salva a data para o sumário e para as movimentações
                        result['summary']['data_competencia_arquivo'] = f"{d[0:4]}-{d[4:6]}-{d[6:8]}" if d.startswith('20') else f"{d[4:8]}-{d[2:4]}-{d[0:2]}"

                # TIPO 1: CONDOMÍNIO
                elif tipo == '1':
                    cnpj = re.sub(r'\D', '', line[COL_CNPJ].strip())
                    if cnpj:
                        current_cnpj = cnpj
                        if cnpj not in cnpjs_vistos: cnpjs_vistos.append(cnpj)

                # TIPO 3: FUNCIONÁRIO
                elif tipo == '3':
                    mat = line[COL_FUNCIONARIO_MATRICULA].strip()
                    nome = line[COL_FUNCIONARIO_NOME].strip()
                    cpf = extrair_cpf_estrito(line)
                    
                    if not cpf:
                        # REGRA: Se o CPF for inválido, gera erro para recusar o TXT
                        result['errors'].append(f"Linha {line_num}: CPF inválido.")
                        # Cacheamos com '000' para evitar erro de "matrícula não encontrada" no Tipo 4
                        continue
                    else:
                        funcs_cache[mat] = {"cpf": cpf, "nome": nome}
                        cpfs_vistos.add(cpf)

                # TIPO 4: BENEFÍCIO
                elif tipo == '4':
                    mat = line[COL_BENEFICIO_MATRICULA].strip()
                    f_data = funcs_cache.get(mat)
                    
                    if not f_data:
                        result['errors'].append(f"Linha {line_num}: Matrícula {mat} não encontrada.")
                        continue

                    # Valor e Dias usando suas fatias
                    v_unit = format_valor_rb(line[COL_BENEFICIO_VALOR])
                    
                    qtd_raw = re.sub(r'\D', '', line[COL_BENEFICIO_NUM_DIAS].strip())
                    qtd = int(qtd_raw) if (qtd_raw and int(qtd_raw) > 0) else 1
                    
                    # Cálculo final
                    v_total = v_unit * qtd

                    result['movimentacoes_detalhada'].append({
                        "cpf_func": f_data['cpf'],
                        "nome_func": f_data['nome'],
                        "valor_recarga_bene": v_total,
                        "cnpj": current_cnpj,
                        "vencimento": result['summary'].get('data_competencia_arquivo')
                    })
                    
                    result['summary']['valor_total_beneficios'] += v_total
                    result['summary']['total_movimentacoes'] += 1

        result['summary']['total_condominios'] = len(cnpjs_vistos)
        result['summary']['total_funcionarios'] = len(cpfs_vistos)
        if cnpjs_vistos:
            result['summary']['primeiro_cnpj_processado'] = cnpjs_vistos[0]

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