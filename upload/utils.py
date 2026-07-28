import decimal
import os
from collections import defaultdict

EXTENSOES_PERMITIDAS = {'.xlsx', '.xlsm', '.txt'}

def validar_extensao_arquivo(file_path, original_filename):
    if not original_filename:
        return original_filename
    
    nome, ext = os.path.splitext(original_filename)
    
    if ext.lower() in EXTENSOES_PERMITIDAS:
        return original_filename
    
    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)
        
        if header[:4] == b'PK\x03\x04':
            return f"{nome}.xlsx"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                f.read(1024)
            return f"{nome}.txt"
        except UnicodeDecodeError:
            return f"{nome}.xlsm"
    except Exception:
        return f"{nome}.xlsm"

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

def get_beneficiary_summary(parsed_data, administradora_cnpj=None):
    from entidades.models import VinculoCondominio, TaxaConfig, Administradora

    total_por_cpf = defaultdict(decimal.Decimal)
    nomes_por_cpf = {}
    condominios_por_cpf = {}
    cnpjs_por_cpf = {}

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
                cnpjs_por_cpf[cpf] = condo.get('cnpj', '')

    taxas_por_cnpj = {}
    if administradora_cnpj:
        admin = Administradora.objects.filter(cnpj=administradora_cnpj).first()
        if admin:
            cnpjs_unicos = set(cnpjs_por_cpf.values())
            for cnpj in cnpjs_unicos:
                if not cnpj:
                    continue
                vinculo = VinculoCondominio.objects.filter(
                    condominio__cnpj=cnpj,
                    administradora=admin
                ).first()
                taxa = decimal.Decimal('0.00')
                if vinculo:
                    taxa_config = TaxaConfig.objects.filter(
                        vinculo=vinculo, ativo=True,
                        produto__isnull=True, tipo__isnull=True
                    ).first()
                    if taxa_config:
                        taxa = taxa_config.taxa_valor
                    elif admin.taxa_padrao_valor > 0:
                        taxa = admin.taxa_padrao_valor
                elif admin.taxa_padrao_valor > 0:
                    taxa = admin.taxa_padrao_valor
                taxas_por_cnpj[cnpj] = float(taxa)

    summary_list = []
    for cpf, total in total_por_cpf.items():
        cnpj = cnpjs_por_cpf.get(cpf, '')
        summary_list.append({
            "nome_funcionario": nomes_por_cpf.get(cpf, "Nome não encontrado"),
            "cpf": cpf,
            "valor_total": str(total),
            "condominio": condominios_por_cpf.get(cpf),
            "cnpj": cnpj,
            "taxa": taxas_por_cnpj.get(cnpj, 0),
            "cep": condominios[-1].get("cep") if condominios else None,
        })
    return summary_list


