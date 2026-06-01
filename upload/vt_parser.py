# upload/vt_parser.py - versão corrigida

import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

def parse_vt_excel(file_path, upload_id):
    """
    Parser para planilha de Vale Transporte no formato novo
    """
    try:
        # Lê todas as abas
        excel_file = pd.ExcelFile(file_path)
        sheets = excel_file.sheet_names
        
        logger.info(f"Abas encontradas: {sheets}")
        
        if 'USUARIOS' not in sheets:
            return {"error": "Planilha não contém a aba 'USUARIOS'"}
        
        # Lê a aba USUARIOS
        df_usuarios = pd.read_excel(file_path, sheet_name='USUARIOS', header=None)
        
        # Encontra a linha de cabeçalho (CNPJ*)
        header_row_idx = None
        for idx, row in df_usuarios.iterrows():
            if row[0] == 'CNPJ*':
                header_row_idx = idx
                break
        
        if header_row_idx is None:
            return {"error": "Não foi possível localizar o cabeçalho da planilha (CNPJ*)"}
        
        # Dados começam após o cabeçalho
        df_dados = df_usuarios.iloc[header_row_idx + 1:].reset_index(drop=True)
        
        # Mapeia índices das colunas
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
            'dias_trabalhados': 9,
            'cpf': 10,
            'rg': 11,
            'digito_rg': 12,
            'estado_rg': 13,
            'data_nascimento': 14,
            'nome_mae': 15,
        }
        
        dados_validados = []
        total_valor_vt = 0
        total_dias = 0
        condominios_set = set()
        # Mapa para agrupar por funcionário (para o summary)
        funcionarios_map = {}
        
        for idx, row in df_dados.iterrows():
            # 🔥 Pula linhas completamente vazias
            if pd.isna(row[col_map['cnpj']]) and pd.isna(row[col_map['nome_completo']]):
                continue
                
            cnpj = row[col_map['cnpj']] if pd.notna(row[col_map['cnpj']]) else None
            nome = row[col_map['nome_completo']] if pd.notna(row[col_map['nome_completo']]) else None
            
            if not cnpj or not nome:
                continue
            
            cpf = row[col_map['cpf']] if pd.notna(row[col_map['cpf']]) else ''
            cpf = str(cpf).replace('.', '').replace('-', '').strip()
            
            # 🔥 Garante que CPF tem 11 dígitos
            if len(cpf) != 11:
                logger.warning(f"CPF inválido para {nome}: {cpf}")
                continue
            
            departamento = row[col_map['departamento']] if pd.notna(row[col_map['departamento']]) else ''
            dias_trabalhados = row[col_map['dias_trabalhados']] if pd.notna(row[col_map['dias_trabalhados']]) else 0
            try:
                dias_trabalhados = int(float(dias_trabalhados)) if dias_trabalhados else 0
            except:
                dias_trabalhados = 0
            
            # Extrai condomínio do departamento
            nome_condominio = ''
            if departamento:
                # Tenta extrair o nome após o CNPJ
                if ' - ' in str(departamento):
                    nome_condominio = str(departamento).split(' - ', 1)[1].strip()
                else:
                    nome_condominio = str(departamento).strip()
            
            if nome_condominio:
                condominios_set.add(nome_condominio)
                
            itens = []
            for item_num in range(1, 11):  # ITEM 1 a ITEM 10
                base_col = 23 + ((item_num - 1) * 4)
                
                if base_col + 3 >= len(row):
                    continue
                
                codigo = row[base_col] if pd.notna(row[base_col]) else None
                quantidade = row[base_col + 1] if pd.notna(row[base_col + 1]) else 1
                dias_item = row[base_col + 2] if pd.notna(row[base_col + 2]) else 0
                valor = row[base_col + 3] if pd.notna(row[base_col + 3]) else None
                
                # 🔥 CORREÇÃO: VALOR já é o valor total do benefício (não multiplicar por quantidade)
                # O campo VALOR na planilha já representa o valor total do item
                if codigo and valor:
                    try:
                        valor_float = float(valor)
                        if valor_float > 0:
                            quantidade_int = int(float(quantidade)) if quantidade and pd.notna(quantidade) else 1
                            dias_int = int(float(dias_item)) if dias_item and pd.notna(dias_item) else dias_trabalhados
                            
                            itens.append({
                                'codigo': str(codigo).strip(),
                                'quantidade': quantidade_int,
                                'dias': dias_int,
                                'valor': valor_float  # VALOR já é o valor total
                            })
                            
                            total_valor_vt += valor_float
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Erro ao converter valor do item {item_num}: {valor} - {e}")
                        continue
            
            # Se não tem itens mas tem dias trabalhados, cria um item padrão
            if not itens and dias_trabalhados > 0:
                valor_por_dia = 6.0  # valor padrão do VT
                valor_total = dias_trabalhados * valor_por_dia
                if valor_total > 0:
                    itens.append({
                        'codigo': 'VT',
                        'quantidade': 1,
                        'dias': dias_trabalhados,
                        'valor': valor_total
                    })
                    total_valor_vt += valor_total
            
            total_dias += dias_trabalhados
            
            # Chave para agrupar por funcionário (para o summary)
            funcionario_key = f"{cpf}_{nome_condominio}"
            if funcionario_key not in funcionarios_map:
                funcionarios_map[funcionario_key] = {
                    'nome_funcionario': str(nome).strip(),
                    'cpf': cpf,
                    'condominio': nome_condominio,
                    'valor_total': 0,
                    'quantidade_dias': 0
                }
            
            # Cria registros para cada item
            for item in itens:
                # 🔥 O VALOR já está correto (é o valor do benefício)
                valor_total_item = item['valor']
                
                # Atualiza o total do funcionário no mapa
                funcionarios_map[funcionario_key]['valor_total'] += valor_total_item
                funcionarios_map[funcionario_key]['quantidade_dias'] += item['dias']
                
                registro = {
                    'cnpj_condominio': str(cnpj).replace('.', '').replace('-', '').replace('/', '')[:14],
                    'nome_condominio': nome_condominio,
                    'cpf_funcionario': cpf,
                    'matricula_funcionario': str(row[col_map['matricula']]) if pd.notna(row[col_map['matricula']]) else str(cpf),
                    'nome_funcionario': str(nome).strip(),
                    'funcao_funcionario': str(row[col_map['cargo']]) if pd.notna(row[col_map['cargo']]) else '',
                    'codigo_produto': item['codigo'],
                    'nome_produto': 'Vale Transporte',
                    'valor_beneficio_total': valor_total_item,
                    'quantidade_dias': item['dias'] if item['dias'] > 0 else dias_trabalhados,
                    'data_competencia': '',
                }
                dados_validados.append(registro)
                
                logger.info(f"Registro VT: {registro['nome_funcionario']} - {registro['codigo_produto']} - R$ {registro['valor_beneficio_total']}")
        
        # Converte o mapa de funcionários para lista
        total_por_beneficiario = list(funcionarios_map.values())
        
        total_funcionarios = len(funcionarios_map)
        
        result = {
            "dados_validados": dados_validados,
            "total_registros": len(dados_validados),
            "total_funcionarios": total_funcionarios,
            "total_condominios": len(condominios_set),
            "valor_total_vt": total_valor_vt,
            "total_dias_trabalhados": total_dias,
            "valido": len(dados_validados) > 0,
            "mensagem_validacao": "Arquivo validado com sucesso",
            "linhas_com_erro": [],
            "total_por_beneficiario": total_por_beneficiario
        }
        
        logger.info(f"VT Parser resultado para upload {upload_id}: total_registros={result['total_registros']}, valido={result['valido']}, valor_total={result['valor_total_vt']}, total_por_beneficiario={len(result['total_por_beneficiario'])}")
        
        return result
        
    except Exception as e:
        logger.error(f"Erro no parse do VT: {str(e)}", exc_info=True)
        return {"error": f"Erro ao processar arquivo VT: {str(e)}"}