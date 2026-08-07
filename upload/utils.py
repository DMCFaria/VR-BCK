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

def _get_taxa_info_for_cnpj(vinculo, admin, cnpj, produtos=None, tipos=None):
    """
    Retorna (taxa_percentual, taxa_tipo) para um vínculo de condomínio.
    Segue a mesma prioridade de get_taxa_cadastrada em export.py:
    1. TaxaConfig com produto específico
    2. TaxaConfig com tipo do produto
    3. TaxaConfig genérica (sem produto, sem tipo)
    4. Taxa padrão da administradora

    produtos e tipos são sets de códigos de produtos/tipos do funcionário.
    Se fornecidos, tenta buscar taxa por produto ou tipo antes da genérica.
    """
    from entidades.models import TaxaConfig

    if not vinculo:
        if admin and admin.taxa_padrao_valor > 0:
            return float(admin.taxa_padrao_valor), admin.taxa_padrao_tipo
        return 0, None

    taxa_encontrada = None

    if produtos:
        for prod_codigo in produtos:
            from beneficios.models import Produto
            prod_obj = Produto.objects.filter(codigo_produto=prod_codigo).first()
            if prod_obj:
                taxa_encontrada = TaxaConfig.objects.filter(
                    vinculo=vinculo, produto=prod_obj, ativo=True
                ).first()
                if taxa_encontrada:
                    break

    if not taxa_encontrada and tipos:
        for tipo in tipos:
            taxa_encontrada = TaxaConfig.objects.filter(
                vinculo=vinculo, tipo=tipo, ativo=True
            ).first()
            if taxa_encontrada:
                break

    if not taxa_encontrada:
        taxa_encontrada = TaxaConfig.objects.filter(
            vinculo=vinculo, produto__isnull=True, tipo__isnull=True, ativo=True
        ).first()

    if taxa_encontrada:
        return float(taxa_encontrada.taxa_valor), taxa_encontrada.taxa_tipo

    if admin and admin.taxa_padrao_valor > 0:
        return float(admin.taxa_padrao_valor), admin.taxa_padrao_tipo

    return 0, None


def get_beneficiary_summary(parsed_data, administradora_cnpj=None):
    from entidades.models import VinculoCondominio, TaxaConfig, Administradora

    total_por_cpf = defaultdict(decimal.Decimal)
    nomes_por_cpf = {}
    condominios_por_cpf = {}
    cnpjs_por_cpf = {}
    produtos_por_cpf = defaultdict(set)
    tipos_por_cpf = defaultdict(set)

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

                for mov in func.get('movimentacoes', []):
                    codigo = mov.get('codigo_produto') or mov.get('codigo') or mov.get('produto', '')
                    tipo = mov.get('tipo', '')
                    if codigo:
                        produtos_por_cpf[cpf].add(codigo)
                    if tipo:
                        tipos_por_cpf[cpf].add(tipo)

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
                ).select_related('condominio').first()

                cpf_com_este_cnpj = next((cpf for cpf, c in cnpjs_por_cpf.items() if c == cnpj), None)
                produtos = produtos_por_cpf.get(cpf_com_este_cnpj, set()) if cpf_com_este_cnpj else set()
                tipos = tipos_por_cpf.get(cpf_com_este_cnpj, set()) if cpf_com_este_cnpj else set()

                taxa_percentual, taxa_tipo = _get_taxa_info_for_cnpj(vinculo, admin, cnpj, produtos, tipos)
                taxas_por_cnpj[cnpj] = (taxa_percentual, taxa_tipo)

    summary_list = []
    for cpf, total in total_por_cpf.items():
        cnpj = cnpjs_por_cpf.get(cpf, '')
        taxa_info = taxas_por_cnpj.get(cnpj, (0, None))
        taxa_percentual, taxa_tipo = taxa_info
        taxa_calculada = decimal.Decimal('0.00')

        if taxa_percentual > 0 and taxa_tipo:
            total_beneficio = total_por_cpf.get(cpf, decimal.Decimal('0'))
            if taxa_tipo == 'FIXO':
                quantidade_dias = sum(mov.get('quantidade', 1) for func in condominios for f in func.get('funcionarios', []) if f.get('cpf') == cpf for mov in f.get('movimentacoes', []))
                quantidade_dias = max(quantidade_dias, 1) if quantidade_dias > 0 else 30
                taxa_calculada = decimal.Decimal(str(taxa_percentual)) * decimal.Decimal(str(quantidade_dias))
            else:
                taxa_calculada = total_beneficio * (decimal.Decimal(str(taxa_percentual)) / decimal.Decimal('100'))

        summary_list.append({
            "nome_funcionario": nomes_por_cpf.get(cpf, "Nome não encontrado"),
            "cpf": cpf,
            "valor_total": str(total),
            "condominio": condominios_por_cpf.get(cpf),
            "cnpj": cnpj,
            "taxa": float(taxa_calculada),
            "taxa_percentual": taxa_percentual,
            "taxa_tipo": taxa_tipo,
            "cep": condominios[-1].get("cep") if condominios else None,
        })
    return summary_list


