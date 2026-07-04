import logging
from django.conf import settings
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.decorators import permission_classes, authentication_classes
from rest_framework.permissions import AllowAny

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

        # Extrair faturamento_id e cnpj de id_integracao (fonte confiável)
        # id_integracao tem o formato: VR_{faturamento.id}_{condominio.cnpj}
        parts = id_integracao.split('_')
        if len(parts) >= 3:
            faturamento_id = parts[1]
            cnpj_cobrado = parts[2]
        else:
            faturamento_id = data.get('faturamento_id')
            cnpj_cobrado = data.get('cnpj_cobrado') or data.get('cnpj')
            if not (faturamento_id and cnpj_cobrado):
                logger.warning(f"id_integracao incorreto para extrair faturamento e CNPJ: {id_integracao}")
                return Response(
                    {"detail": "ID de integração inválido para extração de dados e campos explícitos ausentes."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        numero_nota = data.get('numero_nota')
        pdf_url = data.get('pdf_url') or data.get('url_nota') or data.get('url_danfse')

        # Se o status recebido indicar erro ou falha, notificar o faturista por e-mail
        status_recv = data.get('status', '').upper()
        if status_recv in ('FAILED', 'REJEITADO', 'ERRO', 'CANCELADO', 'CANCELADA'):
            try:
                from core.fedhub.services.fedhub_service import FedhubService
                from django.conf import settings
                fedhub_service = FedhubService()
                dest_email = getattr(settings, 'EMAIL_FATURAMENTO', 'novosnegocios@grupofedcorp.com.br')
                motivo = data.get('mensagem_erro') or data.get('motivo_rejeicao') or 'Erro desconhecido na emissão da prefeitura.'
                
                fedhub_service.enviar_email_erro_nota(
                    email_destinatario=dest_email,
                    faturamento_id=faturamento_id,
                    cnpj_cobrado=cnpj_cobrado,
                    id_integracao=id_integracao,
                    motivo_erro=motivo
                )
                logger.info(f"Notificação de erro de nota enviada para faturista ({dest_email})")
            except Exception as e_notif:
                logger.error(f"Erro ao disparar notificação de erro de nota para faturista: {str(e_notif)}")

        try:
            from beneficios.models import Boleto
            import re
            
            cnpj_limpo = re.sub(r'[^0-9]', '', str(cnpj_cobrado))
            boleto = Boleto.objects.filter(
                faturamento_id=faturamento_id,
                cnpj_cobrado=cnpj_limpo
            ).first()

            if boleto:
                if id_integracao:
                    boleto.NFs_id = str(id_integracao)
                if numero_nota:
                    boleto.Numero_nota = str(numero_nota)
                if pdf_url:
                    boleto.url_nota = str(pdf_url)
                boleto.save()
                logger.info(f"Boleto associado atualizado com sucesso via webhook: Numero_nota={boleto.Numero_nota}")
                return Response(
                    {"detail": "Webhook processado e Boleto atualizado com sucesso."},
                    status=status.HTTP_200_OK
                )
            else:
                logger.warning(f"Nenhum boleto encontrado para faturamento_id={faturamento_id} e cnpj={cnpj_limpo}")
                return Response(
                    {"detail": "Boleto correspondente não encontrado."},
                    status=status.HTTP_404_NOT_FOUND
                )
        except Exception as e_bol:
            logger.error(f"Erro ao atualizar Boleto associado no webhook: {str(e_bol)}")
            return Response(
                {"detail": f"Erro interno ao processar webhook: {str(e_bol)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
