"""
Gravação local dos boletos vindos do FedHub para um Faturamento.

Lógica única usada pela task `processar_faturamento` e pelo comando
`sincronizar_boletos` — antes vivia inline na task e, quando o FedHub devolvia
itens sem `documento`, nada era gravado e nada era avisado (caso do
faturamento 447 / fatura 175826, 25/08/2026).
"""
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


def parse_date_safe(date_str):
    if not date_str:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(str(date_str), fmt).date()
        except ValueError:
            continue
    return None


def gravar_boletos_fedhub(faturamento, fatura_num, boletos_data):
    """
    Faz update_or_create de cada boleto (chave: `documento`) apontando para o
    faturamento. Retorna estatísticas para quem chamou decidir o que fazer.

    Retorno: dict(total, gravados, sem_documento, documentos=[...])
    """
    from beneficios.models import Boleto
    from entidades.models import Condominio

    stats = {'total': len(boletos_data or []), 'gravados': 0, 'sem_documento': 0, 'documentos': []}

    for dados_boleto in boletos_data or []:
        doc_num = dados_boleto.get("documento")
        if not doc_num:
            stats['sem_documento'] += 1
            logger.warning(
                f"[BOLETOS] Fatura {fatura_num}: item do FedHub sem 'documento' foi ignorado. "
                f"Chaves recebidas: {sorted(dados_boleto.keys())}"
            )
            continue

        cnpj_cobrado_raw = dados_boleto.get("cnpj_cobrado") or ""
        cnpj_cobrado_limpo = re.sub(r'[^0-9]', '', str(cnpj_cobrado_raw))
        condominio_exists = Condominio.objects.filter(cnpj=cnpj_cobrado_limpo).exists()

        Boleto.objects.update_or_create(
            documento=doc_num,
            defaults={
                "faturamento": faturamento,
                "fatura": fatura_num,
                "dt_emissao": parse_date_safe(dados_boleto.get("dt_emissao")),
                "codigo_de_barra": dados_boleto.get("codigo_de_barra"),
                "qr_code": dados_boleto.get("qr_code"),
                "qr_imagem": dados_boleto.get("qr_imagem"),
                "vencimento": parse_date_safe(dados_boleto.get("vencimento")),
                "nome_cobrado": dados_boleto.get("nome_cobrado"),
                "cnpj_cobrado": cnpj_cobrado_limpo or cnpj_cobrado_raw,
                "cedente": dados_boleto.get("cedente"),
                "cnpj_cedente": dados_boleto.get("cnpj_cedente"),
                "valor": dados_boleto.get("valor"),
                "deducoes": dados_boleto.get("deducoes"),
                "status": dados_boleto.get("status"),
                "nosso_numero": dados_boleto.get("nosso_numero"),
                "identificador": dados_boleto.get("identificador"),
                "baixa": bool(dados_boleto.get("baixa", False)),
                "dt_baixa": parse_date_safe(dados_boleto.get("dt_baixa")),
                "obs_baixa": dados_boleto.get("obs_baixa"),
                "NFs_id": dados_boleto.get("nfs_id"),
                "Numero_nota": dados_boleto.get("numero_nota"),
                "url_nota": dados_boleto.get("url_nota") or None,
                "match": condominio_exists,
            }
        )
        stats['gravados'] += 1
        stats['documentos'].append(str(doc_num))

    if stats['gravados'] == 0:
        logger.error(
            f"[BOLETOS] Fatura {fatura_num} (faturamento {getattr(faturamento, 'id', '?')}): "
            f"FedHub devolveu {stats['total']} item(ns) e NENHUM boleto foi gravado "
            f"({stats['sem_documento']} sem 'documento'). A consulta de boletos ficará vazia para este pedido."
        )
    else:
        logger.info(
            f"[BOLETOS] Fatura {fatura_num}: {stats['gravados']}/{stats['total']} boletos gravados"
            + (f" ({stats['sem_documento']} ignorados sem 'documento')" if stats['sem_documento'] else "")
        )

    return stats
