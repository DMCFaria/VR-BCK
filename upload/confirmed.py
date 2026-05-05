import logging

from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.fedhub.service.fedhub_service import FedhubService
from .serializers import ProcessamentoFinalSerializer
from .models import FileUpload
from beneficios.models import Importacao

logger = logging.getLogger(__name__)

class ConfirmationView(views.APIView):
    permission_classes = [IsAuthenticated] 
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        payload = request.data 
        logger.info(f"Recebido payload para confirmação: {payload}")
        file_id = payload.get("file_upload_id")
        logger.info(f"Processando confirmação para file_upload_id: {file_id}")

        if not file_id:
            logger.warning("O campo 'file_upload_id' é obrigatório.")
            return Response({"detail": "O campo 'file_upload_id' é obrigatório."}, status=400)

        try:
            file_upload = FileUpload.objects.get(id=file_id)
            if file_upload.process_status == "COMPLETED":
                logger.info(f"Arquivo {file_id} já foi processado anteriormente.")
                return Response(
                    {"detail": "Este arquivo já foi processado anteriormente."}, 
                    status=status.HTTP_400_BAD_REQUEST 
                )
        except FileUpload.DoesNotExist:
            logger.warning(f"Arquivo {file_id} não encontrado.")
            return Response({"detail": "Arquivo não encontrado."}, status=404)
        
        logger.info(f"Validando payload para file_upload_id: {file_id}")

        serializer = ProcessamentoFinalSerializer(data=payload)
        
        logger.info(f"Serializer criado para file_upload_id: {file_id}, validando dados...")

        if serializer.is_valid():
            try:
                result = serializer.save(processed_by=request.user)
                logger.info(f"Processamento finalizado para file_upload_id: {file_id}, resultado: {result}")
                
                fedhub_service = FedhubService()
                
                email_enviado = fedhub_service.enviar_email_upload(
                    email=request.user.email,
                    user=request.user
                )
                                
                # logger.info(f"Email de notificação de upload de faturamento enviado: {email_enviado}")
                
                
                return Response({
                    "detail": "Dados gravados com sucesso.",
                    "registros_processados": result.get("count"),
                    "importacao_id": result.get("importacao_id"),
                    "status": "AGUARDANDO_FATURAMENTO"
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"Erro ao processar arquivo {file_id}: {str(e)}")
                FileUpload.objects.filter(id=file_id).update(process_status="FAILED")
                Importacao.objects.filter(file_upload_id=file_id, status='AGUARDANDO_FATURAMENTO').update(status='FAILED')
                return Response({"detail": f"Erro interno: {str(e)}"}, status=400) 

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)