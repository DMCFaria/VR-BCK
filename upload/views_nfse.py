import logging
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.decorators import permission_classes, authentication_classes
from rest_framework.permissions import AllowAny

from beneficios.models import NotaFiscal

logger = logging.getLogger(__name__)


class NfseWebhookView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
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
        elif novo_status in ('REJEITADO', 'ERRO', 'CANCELADO'):
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

        return Response(
            {"detail": "Webhook processado com sucesso."},
            status=status.HTTP_200_OK
        )
