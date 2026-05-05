import decimal
from collections import defaultdict

def convert_decimals_to_json_safe(data):
    if isinstance(data, dict):
        return {key: convert_decimals_to_json_safe(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_decimals_to_json_safe(element) for element in data]
    elif isinstance(data, decimal.Decimal):
        return str(data) 
    return data

def get_movimentacoes_detalhada(parsed_data):
    """
    Extrai todas as movimentações individuais em um array flat.
    """
    movimentacoes = []
    
    condominios = parsed_data.get('condominios', [])
    
    for condo in condominios:
        nome_condominio = condo.get('nome', '')
        cnpj_condominio = condo.get('cnpj', '')
        cep_condominio = condo.get('cep', '')
        endereco = {
            'rua': condo.get('rua', ''),
            'numero': condo.get('numero', ''),
            'bairro': condo.get('bairro', ''),
            'cidade': condo.get('cidade', ''),
            'estado': condo.get('estado', ''),
            'cep': cep_condominio
        }
        
        for func in condo.get('funcionarios', []):
            nome_funcionario = func.get('nome', '')
            cpf_funcionario = func.get('cpf', '')
            matricula = func.get('matricula', '')
            funcao = func.get('funcao', '')
            
            for mov in func.get('movimentacoes', []):
                movimentacoes.append({
                    "nome_funcionario": nome_funcionario,
                    "cpf_funcionario": cpf_funcionario,
                    "matricula": matricula,
                    "funcao": funcao,
                    "condominio": nome_condominio,
                    "cnpj_condominio": cnpj_condominio,
                    "endereco_condominio": endereco,
                    "codigo_produto": mov.get('codigo_produto', ''),
                    "nome_produto": mov.get('produto', ''),
                    "valor_recarga_bene": str(mov.get('valor', 0)),
                    "data_competencia": parsed_data.get('summary', {}).get('data_competencia_arquivo')
                })
    
    return movimentacoes

def get_beneficiary_summary(parsed_data):
    total_por_cpf = defaultdict(decimal.Decimal)
    nomes_por_cpf = {}
    condominios_por_cpf = {}

    condominios = parsed_data.get('condominios', [])
    for condo in condominios:
        for func in condo.get('funcionarios', []):
            cpf = func.get('cpf')
            nome = func.get('nome')
            valor_bene = func.get('valor_bene', 0)

            if cpf:
                if not isinstance(valor_bene, decimal.Decimal):
                    try:
                        valor_bene = decimal.Decimal(str(valor_bene))
                    except:
                        valor_bene = decimal.Decimal('0.00')
                total_por_cpf[cpf] += valor_bene
                nomes_por_cpf[cpf] = nome
                condominios_por_cpf[cpf] = condo.get('nome', '')

    summary_list = []
    for cpf, total in total_por_cpf.items():
        summary_list.append({
            "nome_funcionario": nomes_por_cpf.get(cpf, "Nome não encontrado"),
            "cpf": cpf,
            "valor_total": str(total),
            "condominio": condominios_por_cpf.get(cpf),
            "cep": condo.get("cep")
        })
    return summary_list


