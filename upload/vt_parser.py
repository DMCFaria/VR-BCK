import logging
import pandas as pd
import numpy as np
import os
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

def validate_cpf(cpf):
    """
    Valida CPF brasileiro
    Mantém zeros à esquerda
    """
    # Remove caracteres não numéricos
    cpf = re.sub(r'[^0-9]', '', str(cpf))
    
    # CPF deve ter 11 dígitos
    if len(cpf) != 11:
        return False
    
    # Verifica se todos os dígitos são iguais (invalido)
    if cpf == cpf[0] * 11:
        return False
    
    # Calcula primeiro dígito verificador
    soma = 0
    for i in range(9):
        soma += int(cpf[i]) * (10 - i)
    resto = 11 - (soma % 11)
    if resto >= 10:
        resto = 0
    if resto != int(cpf[9]):
        return False
    
    # Calcula segundo dígito verificador
    soma = 0
    for i in range(10):
        soma += int(cpf[i]) * (11 - i)
    resto = 11 - (soma % 11)
    if resto >= 10:
        resto = 0
    if resto != int(cpf[10]):
        return False
    
    return True

def parse_currency_value(value):
    """
    Converte valor monetário para float
    """
    if value is None or pd.isna(value):
        return 0.0
    
    # Se for número, converte diretamente
    if isinstance(value, (int, float)):
        return float(value)
    
    valor_str = str(value).strip()
    
    # Remove "R$" e espaços
    valor_str = valor_str.replace('R$', '').strip()
    
    if not valor_str:
        return 0.0
    
    try:
        # Remove pontos de milhar e troca vírgula por ponto
        if ',' in valor_str:
            # Se tem ponto e vírgula (ex: "1.234,56")
            if '.' in valor_str:
                valor_str = valor_str.replace('.', '')
            valor_str = valor_str.replace(',', '.')
        
        return float(valor_str)
    except ValueError:
        logger.warning(f"Não foi possível converter valor: {value}")
        return 0.0

def parse_vt_excel(file_path, upload_id):
    """
    Parser para planilha de Vale Transporte
    """
    try:
        file_ext = os.path.splitext(file_path)[1].lower()
        
        logger.info(f"Processando arquivo VT: {file_path}, extensão: {file_ext}, upload_id: {upload_id}")
        
        # Carrega o Excel
        if file_ext == '.xls':
            df = pd.read_excel(file_path, sheet_name='USUARIOS', header=None, engine='xlrd')
        elif file_ext in ['.xlsx', '.xlsm']:
            df = pd.read_excel(file_path, sheet_name='USUARIOS', header=None, engine='openpyxl')
        else:
            return {"error": f"Formato não suportado: {file_ext}"}
        
        # Encontra o cabeçalho (linha com "CNPJ*")
        header_row_idx = None
        header_row = None
        
        for idx, row in df.iterrows():
            try:
                first_cell = str(row[0]).strip() if len(row) > 0 else ''
                if first_cell == 'CNPJ*' or first_cell == 'CNPJ':
                    header_row_idx = idx
                    header_row = row
                    logger.info(f"Cabeçalho encontrado na linha {idx}")
                    break
            except:
                continue
        
        if header_row_idx is None:
            return {"error": "Não foi possível localizar o cabeçalho (CNPJ*)"}
        
        # Mapeamento das colunas fixas (Template_VT.xlsx layout)
        col_map = {
            'cnpj': 0,
            'matricula': 1,
            'nome_completo': 2,
            'email': 3,
            'celular': 4,
            'ativo': 5,
            'endereco': 6,
            'cargo': 7,
            'departamento': 8,
            'cep_departamento': 9,
            'cidade_departamento': 10,
            'bairro_departamento': 11,
            'uf_departamento': 12,
            'endereco_departamento': 13,
            'dias_trabalhados': 14,
            'cpf': 15,
            'rg': 16,
            'digito_rg': 17,
            'estado_rg': 18,
            'data_nascimento': 19,
            'nome_mae': 20,
            'logradouro': 21,
            'numero': 22,
            'complemento': 23,
            'bairro': 24,
            'cep': 25,
            'cidade': 26,
            'estado': 27,
        }
        
        # Encontra onde começam os itens (coluna com "CÓD.")
        item_start_col = None
        for col_idx in range(20, min(50, len(header_row))):
            cell_value = str(header_row[col_idx]).strip() if col_idx < len(header_row) else ''
            if cell_value == 'CÓD.' or cell_value == 'COD.':
                item_start_col = col_idx
                logger.info(f"Itens começam na coluna {item_start_col}")
                break
        
        if item_start_col is None:
            # Fallback: assume que começam na coluna 28
            item_start_col = 28
            logger.info(f"Usando fallback: itens começam na coluna {item_start_col}")
        
        # Processa as linhas de dados
        linhas_com_erro = []
        dados_validados = []
        total_por_beneficiario = []
        
        # Dicionário para acumular valores por funcionário
        funcionarios_map = defaultdict(lambda: {
            "nome_funcionario": "",
            "cpf": "",
            "cnpj_condominio": "",
            "condominio": "",
            "valor_total": 0.0,
            "quantidade_dias": 0,
            "itens": [],
            "endereco_departamento": "",
            "bairro_departamento": "",
            "cidade_departamento": "",
            "uf_departamento": "",
            "cep_departamento": "",
            "logradouro": "",
            "numero": "",
            "complemento": "",
            "bairro": "",
            "cep": "",
            "cidade": "",
            "estado": "",
        })
        
        condominios_set = set()
        valor_total_vt = 0.0
        total_dias = 0
        linhas_processadas = 0
        
        for idx, row in df.iterrows():
            if idx <= header_row_idx:
                continue
                
            linha_num = idx + 1
            linhas_processadas += 1
            
            # Verifica se a linha tem dados (primeira coluna não vazia)
            primeiro_campo = row[0] if len(row) > 0 and pd.notna(row[0]) else None
            if primeiro_campo is None or str(primeiro_campo).strip() == '':
                continue
            
            try:
                # Dados básicos
                cnpj = str(row[col_map['cnpj']]).strip() if col_map['cnpj'] < len(row) and pd.notna(row[col_map['cnpj']]) else ''
                nome = str(row[col_map['nome_completo']]).strip() if col_map['nome_completo'] < len(row) and pd.notna(row[col_map['nome_completo']]) else ''
                
                if not cnpj or not nome:
                    linhas_com_erro.append({
                        "linha": linha_num,
                        "erro": f"CNPJ ou Nome vazio (CNPJ: '{cnpj}', Nome: '{nome}')",
                        "dados": row.tolist() if len(row) > 0 else []
                    })
                    continue
                
                # CPF - mantém zeros à esquerda
                cpf_val = row[col_map['cpf']] if col_map['cpf'] < len(row) and pd.notna(row[col_map['cpf']]) else ''
                cpf = re.sub(r'[^0-9]', '', str(cpf_val))
                
                # Completa com zeros à esquerda se necessário
                if len(cpf) < 11 and len(cpf) > 0:
                    cpf = cpf.zfill(11)
                
                if not validate_cpf(cpf):
                    linhas_com_erro.append({
                        "linha": linha_num,
                        "erro": f"CPF inválido: {cpf_val} (após limpeza: {cpf})",
                        "dados": row.tolist() if len(row) > 0 else []
                    })
                    continue
                
                # Dias trabalhados
                dias_trab = row[col_map['dias_trabalhados']] if col_map['dias_trabalhados'] < len(row) and pd.notna(row[col_map['dias_trabalhados']]) else 0
                try:
                    dias_trabalhados = int(float(dias_trab)) if dias_trab else 0
                except:
                    dias_trabalhados = 0
                
                # Departamento / Condomínio (formato: "CNPJ - NOME DO CONDOMÍNIO")
                depto_val = row[col_map['departamento']] if col_map['departamento'] < len(row) and pd.notna(row[col_map['departamento']]) else ''
                cnpj_condominio = ''
                nome_condominio = ''
                if depto_val:
                    depto_str = str(depto_val).strip()
                    if ' - ' in depto_str:
                        parts = depto_str.split(' - ', 1)
                        cnpj_raw = re.sub(r'[^0-9]', '', parts[0])
                        cnpj_condominio = cnpj_raw.zfill(14)[:14]
                        nome_condominio = parts[1].strip()
                    else:
                        nome_condominio = depto_str
                
                # Fallback: usa CNPJ da coluna 0 se não veio do departamento
                if not cnpj_condominio:
                    cnpj_condominio = re.sub(r'[^0-9]', '', cnpj)[:14]
                
                if nome_condominio:
                    condominios_set.add(nome_condominio)
                
                # Chave única para o funcionário
                funcionario_key = f"{cpf}_{cnpj_condominio}"
                
                # Processa os itens (cada item tem 4 colunas: CÓD, QTD, DIAS, VALOR)
                itens = []
                
                for item_num in range(1, 11):  # ITEM 1 a ITEM 10
                    base_col = item_start_col + ((item_num - 1) * 4)
                    
                    if base_col + 3 >= len(row):
                        continue
                    
                    codigo = row[base_col] if base_col < len(row) and pd.notna(row[base_col]) else None
                    quantidade = row[base_col + 1] if base_col + 1 < len(row) and pd.notna(row[base_col + 1]) else 1
                    dias_item = row[base_col + 2] if base_col + 2 < len(row) and pd.notna(row[base_col + 2]) else 0
                    valor_unitario = row[base_col + 3] if base_col + 3 < len(row) and pd.notna(row[base_col + 3]) else None
                    
                    # Pula se não tem código ou valor
                    if not codigo or not valor_unitario:
                        continue
                    
                    try:
                        # Converte quantidade
                        try:
                            qtd = int(float(quantidade)) if quantidade and pd.notna(quantidade) else 1
                            if qtd <= 0:
                                qtd = 1
                        except:
                            qtd = 1
                        
                        # Converte dias
                        try:
                            dias = int(float(dias_item)) if dias_item and pd.notna(dias_item) else dias_trabalhados
                        except:
                            dias = dias_trabalhados
                        
                        if dias <= 0:
                            continue
                        
                        # Converte valor unitário
                        valor_unitario_float = parse_currency_value(valor_unitario)
                        
                        if valor_unitario_float <= 0:
                            continue
                        
                        # Cálculo correto
                        valor_total_item = qtd * dias * valor_unitario_float
                        
                        itens.append({
                            'codigo': str(codigo).strip(),
                            'quantidade': qtd,
                            'dias': dias,
                            'valor_unitario': round(valor_unitario_float, 2),
                            'valor_total': round(valor_total_item, 2)
                        })
                        
                        logger.debug(f"Item {item_num}: {qtd} x {dias} x {valor_unitario_float} = {valor_total_item}")
                        
                    except Exception as e:
                        logger.warning(f"Erro no item {item_num} linha {linha_num}: {e}")
                        continue
                
                # Se não tem itens, registra erro
                if not itens:
                    linhas_com_erro.append({
                        "linha": linha_num,
                        "erro": f"Nenhum item válido encontrado (verifique CÓD., QTD., DIAS., VALOR)",
                        "dados": row.tolist() if len(row) > 0 else []
                    })
                    continue
                
                # Atualiza o mapa do funcionário
                funcionarios_map[funcionario_key]["nome_funcionario"] = nome
                funcionarios_map[funcionario_key]["cpf"] = cpf
                funcionarios_map[funcionario_key]["cnpj_condominio"] = cnpj_condominio
                funcionarios_map[funcionario_key]["condominio"] = nome_condominio
                funcionarios_map[funcionario_key]["matricula"] = str(row[col_map['matricula']]) if col_map['matricula'] < len(row) and pd.notna(row[col_map['matricula']]) else ''
                funcionarios_map[funcionario_key]["funcao"] = str(row[col_map['cargo']]) if col_map['cargo'] < len(row) and pd.notna(row[col_map['cargo']]) else ''
                
                # Endereço do departamento (condomínio)
                funcionarios_map[funcionario_key]["endereco_departamento"] = str(row[col_map['endereco_departamento']]) if col_map['endereco_departamento'] < len(row) and pd.notna(row[col_map['endereco_departamento']]) else ''
                funcionarios_map[funcionario_key]["bairro_departamento"] = str(row[col_map['bairro_departamento']]) if col_map['bairro_departamento'] < len(row) and pd.notna(row[col_map['bairro_departamento']]) else ''
                funcionarios_map[funcionario_key]["cidade_departamento"] = str(row[col_map['cidade_departamento']]) if col_map['cidade_departamento'] < len(row) and pd.notna(row[col_map['cidade_departamento']]) else ''
                funcionarios_map[funcionario_key]["uf_departamento"] = str(row[col_map['uf_departamento']]) if col_map['uf_departamento'] < len(row) and pd.notna(row[col_map['uf_departamento']]) else ''
                funcionarios_map[funcionario_key]["cep_departamento"] = str(row[col_map['cep_departamento']]) if col_map['cep_departamento'] < len(row) and pd.notna(row[col_map['cep_departamento']]) else ''
                
                # Endereço do funcionário
                funcionarios_map[funcionario_key]["logradouro"] = str(row[col_map['logradouro']]) if col_map['logradouro'] < len(row) and pd.notna(row[col_map['logradouro']]) else ''
                funcionarios_map[funcionario_key]["numero"] = str(row[col_map['numero']]) if col_map['numero'] < len(row) and pd.notna(row[col_map['numero']]) else ''
                funcionarios_map[funcionario_key]["complemento"] = str(row[col_map['complemento']]) if col_map['complemento'] < len(row) and pd.notna(row[col_map['complemento']]) else ''
                funcionarios_map[funcionario_key]["bairro"] = str(row[col_map['bairro']]) if col_map['bairro'] < len(row) and pd.notna(row[col_map['bairro']]) else ''
                funcionarios_map[funcionario_key]["cep"] = str(row[col_map['cep']]) if col_map['cep'] < len(row) and pd.notna(row[col_map['cep']]) else ''
                funcionarios_map[funcionario_key]["cidade"] = str(row[col_map['cidade']]) if col_map['cidade'] < len(row) and pd.notna(row[col_map['cidade']]) else ''
                funcionarios_map[funcionario_key]["estado"] = str(row[col_map['estado']]) if col_map['estado'] < len(row) and pd.notna(row[col_map['estado']]) else ''
                
                # Para cada item, adiciona movimentação
                for item in itens:
                    valor_total_vt += item['valor_total']
                    total_dias += item['dias']
                    
                    funcionarios_map[funcionario_key]["valor_total"] += item['valor_total']
                    funcionarios_map[funcionario_key]["quantidade_dias"] += item['dias']
                    funcionarios_map[funcionario_key]["itens"].append(item)
                    
                    dados_validados.append({
                        "data_nascimento": str(row[col_map['data_nascimento']]) if col_map['data_nascimento'] < len(row) and pd.notna(row[col_map['data_nascimento']]) else '',
                        "cnpj_condominio": cnpj_condominio,
                        "nome_condominio": nome_condominio,
                        "cpf_funcionario": cpf,
                        "matricula_funcionario": str(row[col_map['matricula']]) if col_map['matricula'] < len(row) and pd.notna(row[col_map['matricula']]) else '',
                        "nome_funcionario": nome,
                        "funcao_funcionario": str(row[col_map['cargo']]) if col_map['cargo'] < len(row) and pd.notna(row[col_map['cargo']]) else '',
                        "codigo_produto": item['codigo'],
                        "nome_produto": 'Vale Transporte',
                        "valor_beneficio_total": round(item['valor_total'], 2),
                        "quantidade_dias": item['dias'],
                        "quantidade": item['quantidade'],
                        "valor_unitario": item['valor_unitario'],
                        # Endereço do departamento (condomínio)
                        "endereco_departamento": str(row[col_map['endereco_departamento']]) if col_map['endereco_departamento'] < len(row) and pd.notna(row[col_map['endereco_departamento']]) else '',
                        "bairro_departamento": str(row[col_map['bairro_departamento']]) if col_map['bairro_departamento'] < len(row) and pd.notna(row[col_map['bairro_departamento']]) else '',
                        "cidade_departamento": str(row[col_map['cidade_departamento']]) if col_map['cidade_departamento'] < len(row) and pd.notna(row[col_map['cidade_departamento']]) else '',
                        "uf_departamento": str(row[col_map['uf_departamento']]) if col_map['uf_departamento'] < len(row) and pd.notna(row[col_map['uf_departamento']]) else '',
                        "cep_departamento": str(row[col_map['cep_departamento']]) if col_map['cep_departamento'] < len(row) and pd.notna(row[col_map['cep_departamento']]) else '',
                        # Endereço do funcionário
                        "logradouro": str(row[col_map['logradouro']]) if col_map['logradouro'] < len(row) and pd.notna(row[col_map['logradouro']]) else '',
                        "numero": str(row[col_map['numero']]) if col_map['numero'] < len(row) and pd.notna(row[col_map['numero']]) else '',
                        "complemento": str(row[col_map['complemento']]) if col_map['complemento'] < len(row) and pd.notna(row[col_map['complemento']]) else '',
                        "bairro": str(row[col_map['bairro']]) if col_map['bairro'] < len(row) and pd.notna(row[col_map['bairro']]) else '',
                        "cep": str(row[col_map['cep']]) if col_map['cep'] < len(row) and pd.notna(row[col_map['cep']]) else '',
                        "cidade": str(row[col_map['cidade']]) if col_map['cidade'] < len(row) and pd.notna(row[col_map['cidade']]) else '',
                        "estado": str(row[col_map['estado']]) if col_map['estado'] < len(row) and pd.notna(row[col_map['estado']]) else '',
                    })
                    
            except Exception as e:
                linhas_com_erro.append({
                    "linha": linha_num,
                    "erro": f"Erro inesperado: {str(e)}",
                    "dados": row.tolist() if len(row) > 0 else []
                })
                logger.error(f"Erro na linha {linha_num}: {e}")
                continue
        
        logger.info(f"Total de linhas processadas: {linhas_processadas}")
        logger.info(f"Total de funcionários únicos: {len(funcionarios_map)}")
        logger.info(f"Total de erros: {len(linhas_com_erro)}")
        
        # Constrói total_por_beneficiario para o frontend
        for key, data in funcionarios_map.items():
            if data["valor_total"] > 0:
                total_por_beneficiario.append({
                    "nome_funcionario": data["nome_funcionario"],
                    "cpf": data["cpf"],
                    "cnpj_condominio": data["cnpj_condominio"],
                    "condominio": data["condominio"],
                    "valor_total": round(data["valor_total"], 2),
                    "quantidade_dias": data["quantidade_dias"]
                })
        
        result = {
            "dados_validados": dados_validados,
            "linhas_com_erro": linhas_com_erro,
            "total_registros": len(dados_validados),
            "total_funcionarios": len(funcionarios_map),
            "total_condominios": len(condominios_set),
            "valor_total_vt": round(valor_total_vt, 2),
            "total_dias_trabalhados": total_dias,
            "valido": len(dados_validados) > 0,
            "mensagem_validacao": f"Processado com {len(linhas_com_erro)} erro(s)" if linhas_com_erro else "Arquivo validado com sucesso",
            "total_por_beneficiario": total_por_beneficiario
        }
        
        logger.info(f"VT Parser finalizado: {result['total_registros']} movimentações, R$ {result['valor_total_vt']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Erro no parse do VT: {str(e)}", exc_info=True)
        return {
            "error": f"Erro ao processar arquivo VT: {str(e)}",
            "dados_validados": [],
            "linhas_com_erro": [],
            "total_registros": 0,
            "total_funcionarios": 0,
            "total_condominios": 0,
            "valor_total_vt": 0,
            "total_dias_trabalhados": 0,
            "valido": False,
            "mensagem_validacao": f"Erro: {str(e)}",
            "total_por_beneficiario": []
        }