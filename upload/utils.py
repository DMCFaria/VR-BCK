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

# Assinaturas de arquivo Excel corrompido/ilegível pelo openpyxl. O caso mais
# comum em produção é o "MultiCellRange" (metadados de células mescladas /
# formatação condicional quebrados dentro do xlsx/xlsm) — o arquivo abre no
# Excel, mas o parser não consegue ler.
_ASSINATURAS_ARQUIVO_CORROMPIDO = (
    "MultiCellRange",
    "File is not a zip file",
    "BadZipFile",
    "expected <class 'openpyxl",
)

ORIENTACAO_ARQUIVO_CORROMPIDO = (
    "Não foi possível ler a planilha: o arquivo parece estar corrompido "
    "(estrutura interna inválida, mesmo abrindo normalmente no Excel). "
    "Como resolver: baixe o modelo oficial em 'Baixar modelos de excel' na "
    "tela de Importação, copie e cole os dados da sua planilha no modelo "
    "novo e importe novamente."
)

def mensagem_erro_arquivo(exc):
    """
    Traduz exceções de leitura do Excel em mensagem amigável para tela.
    Retorna a orientação de arquivo corrompido quando reconhece a assinatura;
    caso contrário, a mensagem genérica com o erro original.
    """
    texto = str(exc)
    if any(a in texto for a in _ASSINATURAS_ARQUIVO_CORROMPIDO):
        return ORIENTACAO_ARQUIVO_CORROMPIDO
    return f"Erro inesperado: {texto}"

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

def _resolver_taxa(vinculo_id, produtos, tipos, taxas_por_vinculo, admin):
    """
    Resolve a taxa aplicável a UM funcionário.

    Retorna (taxa_valor, taxa_tipo, taxa_origem), onde taxa_origem indica de onde
    a taxa veio — usado pelo frontend e pelo suporte para explicar o resultado:
      'produto'        TaxaConfig do vínculo para um produto específico
      'tipo'           TaxaConfig do vínculo para um tipo de produto
      'vinculo'        TaxaConfig genérica do vínculo (todos os produtos)
      'administradora' Taxa padrão da administradora (fallback)
      None             Nenhuma taxa configurada

    Cascata idêntica à de get_taxa_cadastrada em export.py. `produtos` e `tipos`
    são os produtos/tipos DESTE funcionário — não os do condomínio inteiro.
    """
    configs = taxas_por_vinculo.get(vinculo_id, []) if vinculo_id else []

    if configs and produtos:
        for cfg in configs:
            if cfg.produto_id and cfg.produto_id in produtos:
                return float(cfg.taxa_valor), cfg.taxa_tipo, 'produto'

    if configs and tipos:
        for cfg in configs:
            if cfg.tipo and cfg.tipo in tipos:
                return float(cfg.taxa_valor), cfg.taxa_tipo, 'tipo'

    if configs:
        for cfg in configs:
            if not cfg.produto_id and not cfg.tipo:
                return float(cfg.taxa_valor), cfg.taxa_tipo, 'vinculo'

    if admin and admin.taxa_padrao_valor and admin.taxa_padrao_valor > 0:
        return float(admin.taxa_padrao_valor), admin.taxa_padrao_tipo, 'administradora'

    return 0, None, None


def _calcular_valor_taxa(taxa_valor, taxa_tipo, total_beneficio, quantidade_dias):
    """PERC: percentual sobre o benefício. FIXO: valor por dia/movimentação."""
    if not taxa_valor or not taxa_tipo:
        return decimal.Decimal('0.00')

    if taxa_tipo == 'FIXO':
        dias = quantidade_dias if quantidade_dias > 0 else 30
        return decimal.Decimal(str(taxa_valor)) * decimal.Decimal(str(dias))

    return total_beneficio * (decimal.Decimal(str(taxa_valor)) / decimal.Decimal('100'))


def get_beneficiary_summary(parsed_data, administradora_cnpj=None):
    """
    Monta o resumo por beneficiário exibido na tela de importação, já com a taxa
    de administração resolvida para cada funcionário.

    Campos de taxa devolvidos por beneficiário:
      taxa_valor       valor CONFIGURADO (ex.: 3.5 para 3,5% ou 5.00 para R$ 5,00/dia)
      taxa_tipo        'PERC' | 'FIXO' | None
      taxa_calculada   valor em REAIS resultante da aplicação da taxa
      taxa_origem      ver _resolver_taxa()
      taxa             alias de taxa_calculada, mantido por compatibilidade
      taxa_percentual  alias de taxa_valor, mantido por compatibilidade
    """
    from entidades.models import VinculoCondominio, TaxaConfig, Administradora
    from beneficios.models import Produto

    total_por_cpf = defaultdict(decimal.Decimal)
    quantidade_por_cpf = defaultdict(int)
    nomes_por_cpf = {}
    condominios_por_cpf = {}
    cnpjs_por_cpf = {}
    ceps_por_cpf = {}
    produtos_por_cpf = defaultdict(set)

    condominios = parsed_data.get('condominios', [])
    for condo in condominios:
        for func in condo.get('funcionarios', []):
            cpf = func.get('cpf')
            if not cpf:
                continue

            valor_bene = func.get('valor_bene', 0)
            if not isinstance(valor_bene, decimal.Decimal):
                try:
                    valor_bene = decimal.Decimal(str(valor_bene))
                except (decimal.InvalidOperation, TypeError, ValueError):
                    valor_bene = decimal.Decimal('0.00')

            total_por_cpf[cpf] += valor_bene
            nomes_por_cpf[cpf] = func.get('nome')
            condominios_por_cpf[cpf] = condo.get('nome', '')
            cnpjs_por_cpf[cpf] = condo.get('cnpj', '')
            ceps_por_cpf[cpf] = condo.get('cep')

            for mov in func.get('movimentacoes', []):
                codigo = mov.get('codigo_produto') or mov.get('codigo') or mov.get('produto', '')
                if codigo:
                    produtos_por_cpf[cpf].add(str(codigo))
                try:
                    quantidade_por_cpf[cpf] += int(mov.get('quantidade', 1) or 1)
                except (TypeError, ValueError):
                    quantidade_por_cpf[cpf] += 1

    # ---- Pré-carga: uma query por coleção, em vez de N por funcionário ----
    admin = None
    vinculo_por_cnpj = {}
    taxas_por_vinculo = defaultdict(list)
    tipo_por_produto = {}

    if administradora_cnpj:
        admin = Administradora.objects.filter(cnpj=administradora_cnpj).first()

    if admin:
        cnpjs_unicos = {c for c in cnpjs_por_cpf.values() if c}
        if cnpjs_unicos:
            vinculos = VinculoCondominio.objects.filter(
                administradora=admin,
                condominio__cnpj__in=cnpjs_unicos,
            ).values_list('id', 'condominio_id')
            vinculo_por_cnpj = {cnpj: vid for vid, cnpj in vinculos}

        if vinculo_por_cnpj:
            for cfg in TaxaConfig.objects.filter(
                vinculo_id__in=vinculo_por_cnpj.values(), ativo=True
            ):
                taxas_por_vinculo[cfg.vinculo_id].append(cfg)

    todos_produtos = {p for produtos in produtos_por_cpf.values() for p in produtos}
    if todos_produtos:
        tipo_por_produto = dict(
            Produto.objects.filter(codigo_produto__in=todos_produtos)
            .values_list('codigo_produto', 'tipo')
        )

    # ---- Resolução por funcionário ----
    summary_list = []
    for cpf, total in total_por_cpf.items():
        cnpj = cnpjs_por_cpf.get(cpf, '')
        produtos = produtos_por_cpf.get(cpf, set())
        tipos = {tipo_por_produto.get(p) for p in produtos if tipo_por_produto.get(p)}

        taxa_valor, taxa_tipo, taxa_origem = _resolver_taxa(
            vinculo_por_cnpj.get(cnpj), produtos, tipos, taxas_por_vinculo, admin
        )

        taxa_calculada = _calcular_valor_taxa(
            taxa_valor, taxa_tipo, total, quantidade_por_cpf.get(cpf, 0)
        )

        summary_list.append({
            "nome_funcionario": nomes_por_cpf.get(cpf, "Nome não encontrado"),
            "cpf": cpf,
            "valor_total": str(total),
            "condominio": condominios_por_cpf.get(cpf),
            "cnpj": cnpj,
            "taxa_valor": taxa_valor,
            "taxa_tipo": taxa_tipo,
            "taxa_calculada": float(taxa_calculada),
            "taxa_origem": taxa_origem,
            # Compatibilidade com consumidores antigos
            "taxa": float(taxa_calculada),
            "taxa_percentual": taxa_valor,
            "cep": ceps_por_cpf.get(cpf),
        })

    return summary_list


