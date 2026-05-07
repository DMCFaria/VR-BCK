import logging

from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.fedhub.services.fedhub_service import FedhubService
from .serializers import ProcessamentoFinalSerializer
from .models import FileUpload
from beneficios.models import Importacao
from django.utils import timezone

logger = logging.getLogger(__name__)

class ConfirmationView(views.APIView):
    permission_classes = [IsAuthenticated] 
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        payload = request.data 
        # logger.info(f"Recebido payload para confirmação: {payload}")
        file_id = payload.get("file_upload_id")
        # logger.info(f"Processando confirmação para file_upload_id: {file_id}")

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
        
        # logger.info(f"Validando payload para file_upload_id: {file_id}")

        serializer = ProcessamentoFinalSerializer(data=payload)
        
        # logger.info(f"Serializer criado para file_upload_id: {file_id}, validando dados...")

        if serializer.is_valid():
            
            # logger.info(f"Payload válido para file_upload_id: {file_id}, iniciando processamento final...")
            
            # summary = payload.get('summary', {})
            # logger.info(f"Summary para file_upload_id: {file_id}: {summary}")
            
            try:
                result = serializer.save(processed_by=request.user)
                # logger.info(f"Processamento finalizado para file_upload_id: {file_id}, resultado: {result}")
                       
                # Extrai dados do payload para o email
                summary = payload.get('summary', {})
                
                # Calcula totais
                total_condominios = len(payload.get('condominios', []))
                total_funcionarios = summary.get('total_funcionarios', 0)
                total_movimentacoes = summary.get('total_movimentacoes', 0)
                valor_total = float(summary.get('valor_total_beneficios', 0))
                
                # Data de competência
                competencia_mes = payload.get('competencia_mes', '')
                competencia_ano = payload.get('competencia_ano', '')
                competencia_str = f"{competencia_mes}/{competencia_ano}" if competencia_mes and competencia_ano else "—"
                
                # Tipo de processamento
                tipo_processamento = payload.get('tipo_processamento', 'compra')
                tipo_display = "Compra de Benefícios" if tipo_processamento == "compra" else "Faturamento"

                fedhub_service = FedhubService()
                
                # Envia email com dados REAIS
                email_enviado = fedhub_service.enviar_email_upload(
                    email=request.user.email,
                    user=request.user,
                    dados_processamento={
                        "arquivo_nome": file_upload.file.name if file_upload.file else "arquivo.xlsx",
                        "data_envio": timezone.now().strftime('%d/%m/%Y %H:%M'),
                        "competencia": competencia_str,
                        "total_registros": total_movimentacoes,
                        "total_funcionarios": total_funcionarios,
                        "total_condominios": total_condominios,
                        "valor_total": valor_total,
                        "tipo_processamento": tipo_display,
                        "faturamento_id": result.get("importacao_id"),
                        "vencimento": payload.get('vencimento', ''),
                        "periodo_inicio": payload.get('periodo_inicio', ''),
                        "periodo_fim": payload.get('periodo_fim', '')
                    }
                )
                logger.info(f"Email de notificação enviado para {request.user.email}: {email_enviado}")
                
                return Response({
                    "detail": "Dados gravados com sucesso.",
                    "registros_processados": result.get("count"),
                    "importacao_id": result.get("importacao_id"),
                    "status": "AGUARDANDO_FATURAMENTO",
                    "email_enviado": email_enviado
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"Erro ao processar arquivo {file_id}: {str(e)}")
                FileUpload.objects.filter(id=file_id).update(process_status="FAILED")
                Importacao.objects.filter(file_upload_id=file_id, status='AGUARDANDO_FATURAMENTO').update(status='FAILED')
                return Response({"detail": f"Erro interno: {str(e)}"}, status=400) 

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)