import re
from decimal import Decimal
from datetime import datetime
from collections import defaultdict # Para somar os totais para o summary

# --- CONSTANTES DE MAPEAMENTO (Mantidas do anterior) ---
COL_SEQUENCIAL = slice(0, 5)
COL_TIPO_REGISTRO = slice(5,6)
COL_CNPJ = slice(6, 19)
COL_DATA_COMPETENCIA = slice(6, 14)

# Tipo 1: CONDOMÍNIO
COL_CONDOMINIO_RAZAO_SOCIAL = slice(20, 60)

# Tipo 2: ENDEREÇO
COL_ENDERECO_CEP = slice(22, 30)
COL_ENDERECO_RUA = slice(30, 90)
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

def format_date(text, date_format="%Y%m%d"):
    text = clean_and_strip(text)
    if not text: return None
    try:
        return datetime.strptime(text, date_format).strftime("%d-%m-%Y")
    except ValueError: return None

def parse_rb_layout(file_path, file_upload_id):
    """
    Realiza o parsing do arquivo de largura fixa.
    Retorna uma lista de movimentações detalhadas (Flat/Planilha) para exibição e persistência.
    """
    
    
    condominios_cache = {} 
    funcionarios_cache = {} 
    
    movimentacoes_detalhada = [] 
    
    data_competencia = None
    current_cnpj = None
    
    total_valor = Decimal(0)
    total_movimentacoes = 0
    total_funcionarios = set()
    total_condominios = set()

    try:
        with open(file_path, 'r', encoding='latin-1') as f:
            lines = f.readlines()
            
            for i, line in enumerate(lines):
                if not line.strip(): continue

                tipo_registro = clean_and_strip(line[COL_TIPO_REGISTRO])
                cnpj_raw = clean_and_strip(line[COL_CNPJ])
                
                if i == 0:
                    dt_raw = clean_and_strip(line[COL_DATA_COMPETENCIA])
                    if dt_raw:
                        data_competencia= format_date(dt_raw)
                        

                if tipo_registro == '1':
                    current_cnpj = cnpj_raw
                    if current_cnpj:
                        total_condominios.add(current_cnpj)
                        condominios_cache[current_cnpj] = {
                            'cnpj': current_cnpj,
                            'razao_social': clean_and_strip(line[COL_CONDOMINIO_RAZAO_SOCIAL]),
                            'endereco': '', 'bairro': '', 'cidade': '', 'uf': '', 'cep': ''
                        }

            
                elif tipo_registro == '2' and current_cnpj in condominios_cache:
                    c = condominios_cache[current_cnpj]
                    c['cep'] = clean_and_strip(line[COL_ENDERECO_CEP])
                    c['endereco'] = f"{clean_and_strip(line[COL_ENDERECO_RUA])}, {clean_and_strip(line[COL_ENDERECO_NUMERO])}"
                    c['bairro'] = clean_and_strip(line[COL_ENDERECO_BAIRRO])
                    c['cidade'] = clean_and_strip(line[COL_ENDERECO_MUNICIPIO])
                    c['uf'] = clean_and_strip(line[COL_ENDERECO_UF])

                
                elif tipo_registro == '3':
                    mat = clean_and_strip(line[COL_FUNCIONARIO_MATRICULA])
                    cpf = clean_and_strip(line[COL_FUNCIONARIO_CPF])
                    if mat and cpf:
                        total_funcionarios.add(cpf)
                        funcionarios_cache[mat] = {
                            'cpf': cpf,
                            'nome': clean_and_strip(line[COL_FUNCIONARIO_NOME]),
                            'funcao': clean_and_strip(line[COL_FUNCIONARIO_FUNCAO]),
                            'data_nascimento': format_date(line[COL_FUNCIONARIO_DATA_NASCIMENTO]),
                            'matricula': mat
                        }

               
                elif tipo_registro == '4':
                    mat_beneficio = clean_and_strip(line[COL_BENEFICIO_MATRICULA])
                    func_data = funcionarios_cache.get(mat_beneficio)
                    cond_data = condominios_cache.get(current_cnpj)

                    if func_data and cond_data and data_competencia:
                        valor_unitario = format_valor(line[COL_BENEFICIO_VALOR])
                        quantidade = int(clean_and_strip(line[COL_BENEFICIO_NUM_DIAS]) or 0)
                        valor_total_linha = valor_unitario * (quantidade if quantidade > 0 else 1)

                        
                        linha_detalhada = {
                           
                            "cpf_func": func_data['cpf'],
                            "nome_func": func_data['nome'], 
                            "produto": clean_and_strip(line[COL_BENEFICIO_NOME]),
                            "beneficio_nome": clean_and_strip(line[COL_BENEFICIO_NOME]),
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
                            
                            
                            "produto_codigo": clean_and_strip(line[COL_BENEFICIO_CODIGO]),
                            "matricula": func_data['matricula'],
                            "funcao": func_data['funcao'],
                        }
                        
                        movimentacoes_detalhada.append(linha_detalhada)
                        total_valor += valor_total_linha
                        total_movimentacoes += 1

        
        summary = {
            "total_condominios": len(total_condominios),
            "total_funcionarios": len(total_funcionarios),
            "total_movimentacoes": total_movimentacoes,
            "valor_total_beneficios": total_valor,
            "data_competencia_arquivo": data_competencia,
        }

    
        return {
            "file_upload_id": file_upload_id,
            "movimentacoes_detalhada": movimentacoes_detalhada,
            "summary": summary
        }

    except Exception as e:
        return {'error': f'Falha no parsing: {str(e)}'}