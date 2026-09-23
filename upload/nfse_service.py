import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _build_nota_payload(faturamento, condominio, valor_servico, servico_discriminacao, servico_codigo, numero_fatura):
    prestador_cpf_cnpj = getattr(settings, 'NFSE_PRESTADOR_CPF_CNPJ', '35315360000167')
    prestador_razao_social = getattr(settings, 'NFSE_PRESTADOR_RAZAO_SOCIAL', 'FEDCORP ADMINISTRADORA DE CARTOES LTDA')
    tomador_codigo = getattr(settings, 'NFSE_TOMADOR_CODIGO_PADRAO', '3550308')
    servico_codigo = servico_codigo or getattr(settings, 'NFSE_SERVICO_CODIGO', '100202')

    return {
        "id_integracao": f"VR_{faturamento.id}_{condominio.cnpj}",
        "prestador_cpf_cnpj": ''.join(filter(str.isdigit, str(prestador_cpf_cnpj))),
        "prestador_razao_social": prestador_razao_social,
        "tomador_cpf_cnpj": ''.join(filter(str.isdigit, str(condominio.cnpj))),
        "tomador_razao_social": condominio.nome,
        "tomador_logradouro": condominio.endereco or '',
        "tomador_numero": condominio.numero or '',
        "tomador_bairro": condominio.bairro or '',
        "tomador_cep": ''.join(filter(str.isdigit, str(condominio.cep or ''))),
        "tomador_cidade": condominio.cidade or '',
        "tomador_estado": condominio.estado or '',
        "tomador_codigo": tomador_codigo,
        "servico_codigo": servico_codigo,
        "servico_discriminacao": servico_discriminacao,
        "valor_servico": float(valor_servico),
        "fatura": numero_fatura,
        "documento": f"NF{numero_fatura}",
    }


def emitir_nfse_lote(faturamento, dados_condominios, servico_codigo=None):
    """Envia o lote à API de NFSe e devolve {ok, erro, status_code, resposta}.

    Nunca lança: falhas de rede ou HTTP voltam em `erro` para o chamador logar.
    O número da nota chega depois, via webhook (NfseWebhookView).
    """
    api_url = getattr(settings, 'NFSE_API_URL', 'https://fedcorp-nfs-e-django-ebh2e.ondigitalocean.app/api/nfse/emissao/vr/')

    notas_payload = []

    for item in dados_condominios:
        condominio, valor_servico, discriminacao, numero_fatura = item
        nota_data = _build_nota_payload(
            faturamento, condominio, valor_servico, discriminacao, servico_codigo, numero_fatura
        )
        notas_payload.append(nota_data)

    if not notas_payload:
        logger.warning("Nenhum condomínio para emitir NFSe.")
        return {"ok": False, "erro": "nenhuma nota no lote", "status_code": None, "resposta": None}

    payload = {"notas": notas_payload}

    headers = {
        'Content-Type': 'application/json',
        'X-API-KEY': getattr(settings, 'NFSE_X_API_KEY', 'fedcorp_static_token_secure_xyz123'),
    }

    try:
        response = requests.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=60,
        )
    except requests.RequestException as e:
        logger.error(f"Erro de conexão ao enviar lote NFSe para faturamento {faturamento.id}: {e}")
        return {"ok": False, "erro": str(e), "status_code": None, "resposta": None}

    try:
        corpo = response.json()
    except ValueError:
        corpo = response.text

    if response.ok:
        logger.info(
            f"NFSe lote aceito: {len(notas_payload)} notas, status_code={response.status_code}, "
            f"faturamento={faturamento.id}, resposta={corpo}"
        )
        return {"ok": True, "erro": None, "status_code": response.status_code, "resposta": corpo}

    logger.error(
        f"NFSe lote rejeitado: status_code={response.status_code}, faturamento={faturamento.id}, "
        f"resposta={corpo}"
    )
    return {
        "ok": False,
        "erro": f"HTTP {response.status_code}: {corpo}",
        "status_code": response.status_code,
        "resposta": corpo,
    }
