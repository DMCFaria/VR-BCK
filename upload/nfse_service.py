import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _build_nota_payload(faturamento, condominio, valor_servico, servico_discriminacao, servico_codigo):
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
        "fatura": str(faturamento.id),
        "documento": f"NF{faturamento.id}",
    }


def emitir_nfse_lote(faturamento, dados_condominios, servico_codigo=None):
    from beneficios.models import NotaFiscal

    api_url = getattr(settings, 'NFSE_API_URL', 'https://fedcorp-nfs-e-django-ebh2e.ondigitalocean.app/api/nfse/emissao/vr/')

    notas_payload = []
    notas_fiscais_criadas = []

    for condominio, valor_servico, discriminacao in dados_condominios:
        nota_data = _build_nota_payload(
            faturamento, condominio, valor_servico, discriminacao, servico_codigo
        )
        notas_payload.append(nota_data)

        nf = NotaFiscal.objects.create(
            faturamento=faturamento,
            condominio=condominio,
            id_integracao=nota_data["id_integracao"],
            status='EM_EMISSAO',
            payload={"notas": [nota_data]},
        )
        notas_fiscais_criadas.append(nf)

    if not notas_payload:
        logger.warning("Nenhum condomínio para emitir NFSe.")
        return []

    payload = {"notas": notas_payload}

    try:
        response = requests.post(
            api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=60,
        )
        response.raise_for_status()
        resposta_data = response.json()

        for nf in notas_fiscais_criadas:
            nf.resposta = resposta_data
            nf.save(update_fields=['resposta'])

        logger.info(
            f"NFSe lote enviado: {len(notas_payload)} notas, "
            f"status_code={response.status_code}, faturamento={faturamento.id}"
        )
    except requests.RequestException as e:
        erro_msg = str(e)
        for nf in notas_fiscais_criadas:
            nf.erro = erro_msg
            nf.status = 'FAILED'
            nf.save(update_fields=['erro', 'status'])
        logger.error(f"Erro ao enviar lote NFSe para faturamento {faturamento.id}: {erro_msg}")

    return notas_fiscais_criadas
