import re
from decimal import Decimal
from datetime import datetime
from collections import defaultdict

from entidades.models import Condominio, Funcionario
from beneficios.models import Produto

# --- CONSTANTES DE MAPEAMENTO ---
COL_SEQUENCIAL = slice(0, 5)
COL_TIPO_REGISTRO_WIDER = slice(5, 7)
COL_CNPJ = slice(6, 19)

# Tipo 1: CONDOMÍNIO
COL_CONDOMINIO_RAZAO_SOCIAL = slice(20, 60)

# Tipo 2: ENDEREÇO
COL_ENDERECO_CEP = slice(22, 30)
COL_ENDERECO_RUA = slice(31, 90)
COL_ENDERECO_NUMERO = slice(90, 100)
COL_ENDERECO_BAIRRO = slice(130, 160)
COL_ENDERECO_MUNICIPIO = slice(170, 190)
COL_ENDERECO_UF = slice(210, 213)

# Tipo 3: FUNCIONÁRIO
COL_FUNCIONARIO_MATRICULA = slice(19, 32)
COL_FUNCIONARIO_NOME = slice(32, 80)
COL_FUNCIONARIO_FUNCAO = slice(132, 160)
COL_FUNCIONARIO_DATA_NASCIMENTO = slice(172, 180)
COL_FUNCIONARIO_CPF = slice(183, 195)

# Tipo 4: BENEFÍCIO
COL_BENEFICIO_MATRICULA = slice(19, 32)
COL_BENEFICIO_CODIGO = slice(39, 44)
COL_BENEFICIO_NOME = slice(44, 90)
COL_BENEFICIO_NUM_DIAS = slice(104, 108)
COL_BENEFICIO_VALOR = slice(108, 116)

def clean_and_strip(text):
    return text.strip() if text else ""

def format_valor(text):
    text = clean_and_strip(text)
    if not text: return Decimal(0)
    try:
        return Decimal(f"{text[:-2]}.{text[-2:]}")
    except: return Decimal(0)

def format_date(text, date_format="%d%m%Y"):
    text = clean_and_strip(text)
    if not text: return None
    try:
        return datetime.strptime(text, date_format).strftime("%Y-%m-%d")
    except ValueError: return None

def parse_rb_layout(file_path, file_upload_id):
    """
    Realiza o parsing, identifica novos registros e gera a estrutura plana.
    """
    
    db_cnpjs = set(Condominio.objects.values_list('cnpj', flat=True))
    db_cpfs = set(Funcionario.objects.values_list('cpf', flat=True))
    db_produtos = set(Produto.objects.values_list('codigo_produto', flat=True))

    novos_condominios = {} 
    novos_funcionarios = {}
    novos_produtos = {}

    condominios_cache = {} 
    funcionarios_cache = {} 
    movimentacoes_detalhada = [] 
    
    data_competencia = None
    current_cnpj = None
    
    total_valor = Decimal(0)
    total_movimentacoes = 0
    
    count_funcs_file = set()
    count_condos_file = set()

    try:
        with open(file_path, 'r', encoding='latin-1') as f:
            lines = f.readlines()
            
            for i, line in enumerate(lines):
                if not line.strip(): continue

                raw_type = clean_and_strip(line[COL_TIPO_REGISTRO_WIDER])
                tipo_registro = raw_type[0] if raw_type and raw_type[0].isdigit() else ''
                cnpj_raw = clean_and_strip(line[COL_CNPJ])
                
                if i == 0:
                    match_ano_inicio = re.search(r'(20[2-9]\d)(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])', line)
                    if match_ano_inicio:
                        ano, mes, dia = match_ano_inicio.groups()
                        data_competencia = f"{ano}-{mes}-01"
                    else:
                        dt_raw = clean_and_strip(line[6:14]) 
                        d = format_date(dt_raw, "%Y%m%d") 
                        if d: data_competencia = d[:-2] + '01'

                if tipo_registro == '1':
                    current_cnpj = cnpj_raw
                    if current_cnpj:
                        count_condos_file.add(current_cnpj)
                        nome_condo = clean_and_strip(line[COL_CONDOMINIO_RAZAO_SOCIAL])
                        
                        condominio_obj = {
                            'cnpj': current_cnpj,
                            'razao_social': nome_condo,
                            'endereco': '', 'numero': '', 'bairro': '', 
                            'cidade': '', 'uf': '', 'cep': '', 'rua': ''
                        }
                        condominios_cache[current_cnpj] = condominio_obj
                        
                        if current_cnpj not in db_cnpjs:
                            novos_condominios[current_cnpj] = condominio_obj

                elif tipo_registro == '2' and current_cnpj in condominios_cache:
                    c = condominios_cache[current_cnpj]
                    c['cep'] = clean_and_strip(line[COL_ENDERECO_CEP])
                    c['rua'] = clean_and_strip(line[COL_ENDERECO_RUA])
                    c['numero'] = clean_and_strip(line[COL_ENDERECO_NUMERO])
                    c['endereco'] = f"{c['rua']}, {c['numero']}" 
                    c['bairro'] = clean_and_strip(line[COL_ENDERECO_BAIRRO])
                    c['cidade'] = clean_and_strip(line[COL_ENDERECO_MUNICIPIO])
                    c['uf'] = clean_and_strip(line[COL_ENDERECO_UF])

                elif tipo_registro == '3':
                    mat = clean_and_strip(line[COL_FUNCIONARIO_MATRICULA])
                    cpf = clean_and_strip(line[COL_FUNCIONARIO_CPF])
                    
                    if mat and cpf:
                        count_funcs_file.add(cpf)
                        nome_func = clean_and_strip(line[COL_FUNCIONARIO_NOME])
                        
                        funcionarios_cache[mat] = {
                            'cpf': cpf,
                            'nome': nome_func,
                            'funcao': clean_and_strip(line[COL_FUNCIONARIO_FUNCAO]),
                            'data_nascimento': format_date(line[COL_FUNCIONARIO_DATA_NASCIMENTO]),
                            'matricula': mat
                        }
                        
                        if cpf not in db_cpfs:
                            condo_atual = condominios_cache.get(current_cnpj, {})
                            novos_funcionarios[cpf] = {
                                'cpf': cpf, 
                                'nome': nome_func,
                                'valor_total_linha': Decimal(0), 
                                'departamento': condo_atual.get('razao_social', ''), 
                                'cnpj': current_cnpj, 
                            }

                elif tipo_registro == '4':
                    mat_beneficio = clean_and_strip(line[COL_BENEFICIO_MATRICULA])
                    func_data = funcionarios_cache.get(mat_beneficio)
                    cond_data = condominios_cache.get(current_cnpj)
                    
                    valor_total_linha = Decimal(0)
                    valor_unitario = Decimal(0)
                    quantidade = 0

                    if func_data and cond_data and data_competencia:
                        valor_unitario = format_valor(line[COL_BENEFICIO_VALOR])
                        quantidade = int(clean_and_strip(line[COL_BENEFICIO_NUM_DIAS]) or 0)
                        valor_total_linha = valor_unitario * (quantidade if quantidade > 0 else 1)
                        
                        cod_prod = clean_and_strip(line[COL_BENEFICIO_CODIGO])
                        nome_prod = clean_and_strip(line[COL_BENEFICIO_NOME])

                        if cod_prod not in db_produtos:
                            novos_produtos[cod_prod] = {'codigo': cod_prod, 'nome': nome_prod}

                        cpf_atual = func_data['cpf']
                        if cpf_atual in novos_funcionarios:
                            novos_funcionarios[cpf_atual]['valor_total_linha'] += valor_total_linha

                        linha_detalhada = {
                            "cpf_func": func_data['cpf'], 
                            "nome_func": func_data['nome'], 
                            "produto": nome_prod, 
                            "beneficio_nome": nome_prod, 
                            "valor_unitario": valor_unitario, 
                            "quantidade": quantidade, 
                            "valor_recarga_bene": valor_total_linha, 
                            "repasse_vt": Decimal(0), 
                            "taxa": Decimal(0), 
                            "departamento": cond_data['razao_social'], 
                            "cnpj": cond_data['cnpj'], 
                            "endereco": cond_data['endereco'], 
                            "bairro": cond_data['bairro'], 
                            "cidade": cond_data['cidade'], 
                            "uf": cond_data['uf'], 
                            "cep": cond_data['cep'], 
                            "vencimento": data_competencia, 
                            "periodos": data_competencia, 
                            "periodo2": data_competencia, 
                            "produto_codigo": cod_prod,
                            "matricula": func_data['matricula'],
                            "funcao": func_data['funcao'],
                            # ADICIONADO: Data de Nascimento no objeto detalhado
                            "data_nascimento": func_data['data_nascimento'] 
                        }
                        
                        movimentacoes_detalhada.append(linha_detalhada)
                        total_valor += valor_total_linha
                        total_movimentacoes += 1

        summary = {
            "total_condominios": len(count_condos_file),
            "total_funcionarios": len(count_funcs_file),
            "total_movimentacoes": total_movimentacoes,
            "valor_total_beneficios": total_valor.quantize(Decimal('0.00')),
            "data_competencia_arquivo": data_competencia,
            "primeiro_cnpj_processado": list(count_condos_file)[0] if count_condos_file else "N/A"
        }

        return {
            "file_upload_id": file_upload_id,
            "movimentacoes_detalhada": movimentacoes_detalhada,
            "summary": summary,
            "novos_registros": {
                "Total de funcionários novos": len(novos_funcionarios),
                "Total de condomínios novos": len(novos_condominios),
                "condominios": list(novos_condominios.values()),
                "funcionarios": list(novos_funcionarios.values()),
                "produtos": list(novos_produtos.values())
            }
        }

    except Exception as e:
        return {'error': f'Falha no parsing: {str(e)}'}