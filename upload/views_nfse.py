import logging
from django.conf import settings
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.decorators import permission_classes, authentication_classes
from rest_framework.permissions import AllowAny

from beneficios.models import NotaFiscal

logger = logging.getLogger(__name__)


class NfseWebhookView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # Validação do token de segurança X-API-KEY
        api_key = request.headers.get('X-API-KEY') or request.META.get('HTTP_X_API_KEY')
        expected_key = getattr(settings, 'NFSE_X_API_KEY', 'fedcorp_static_token_secure_xyz123')
        if api_key != expected_key:
            logger.warning(f"Chave de API inválida ou ausente no webhook de NFSe: {api_key}")
            return Response(
                {"detail": "Acesso não autorizado."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        data = request.data
        logger.info(f"Webhook NFSe recebido: {data}")

        id_integracao = data.get('id_integracao')
        if not id_integracao:
            return Response(
                {"detail": "Campo 'id_integracao' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            nota_fiscal = NotaFiscal.objects.get(id_integracao=id_integracao)
        except NotaFiscal.DoesNotExist:
            logger.warning(f"NotaFiscal com id_integracao={id_integracao} não encontrada.")
            return Response(
                {"detail": "Nota fiscal não encontrada."},
                status=status.HTTP_404_NOT_FOUND
            )

        novo_status = data.get('status', '').upper()
        if novo_status in dict(NotaFiscal.STATUS_CHOICES):
            nota_fiscal.status = novo_status
        elif novo_status == 'EMITIDO':
            nota_fiscal.status = 'EMITIDO'
        elif novo_status in ('REJEITADO', 'ERRO', 'CANCELADO', 'FAILED'):
            nota_fiscal.status = 'FAILED'

        if data.get('protocolo'):
            nota_fiscal.protocolo = str(data.get('protocolo'))
        if data.get('numero_nota'):
            nota_fiscal.numero_nota = str(data.get('numero_nota'))
        if data.get('codigo_verificacao'):
            nota_fiscal.codigo_verificacao = str(data.get('codigo_verificacao'))
        if data.get('pdf_url'):
            nota_fiscal.pdf_url = str(data.get('pdf_url'))

        nota_fiscal.resposta = data
        nota_fiscal.save()

        logger.info(f"NotaFiscal {nota_fiscal.id_integracao} atualizada: status={nota_fiscal.status}")

        # Atualizar a tabela Boleto correspondente
        try:
            from beneficios.models import Boleto
            import re
            
            cnpj_limpo = re.sub(r'[^0-9]', '', str(nota_fiscal.condominio.cnpj))
            boleto = Boleto.objects.filter(
                faturamento=nota_fiscal.faturamento,
                cnpj_cobrado=cnpj_limpo
            ).first()

            if boleto:
                if nota_fiscal.status == 'EMITIDO':
                    boleto.Numero_nota = nota_fiscal.numero_nota
                    boleto.url_nota = nota_fiscal.pdf_url
                boleto.save()
                logger.info(f"Boleto associado atualizado com sucesso: Numero_nota={boleto.Numero_nota}")
        except Exception as e_bol:
            logger.error(f"Erro ao atualizar Boleto associado no webhook: {str(e_bol)}")

        return Response(
            {"detail": "Webhook processado com sucesso."},
            status=status.HTTP_200_OK
        )
