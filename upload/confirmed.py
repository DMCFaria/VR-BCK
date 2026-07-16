import logging
import traceback

from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.fedhub.services.fedhub_service import FedhubService
from .serializers import ProcessamentoFinalSerializer
from .models import FileUpload
from beneficios.models import Importacao
from django.utils import timezone

from django.conf import settings

logger = logging.getLogger(__name__)


def _gerar_e_upload_planilha_editada(file_upload, dados_modificados, data_competencia, request_user):
    """Gera planilha editada e faz upload para S3."""
    import boto3
    from datetime import datetime
    from urllib.parse import quote
    from .gerar_planilha_editada import gerar_planilha_vr

    try:
        planilha_bytes = gerar_planilha_vr(dados_modificados, data_competencia)

        s3 = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )

        original_name = file_upload.file.name.split('.')[0] if file_upload.file else 'importacao'
        user = request_user
        admin_nome_completo = str(user.administradora_ativa) if user.administradora_ativa else 'SISTEMA'
        duas_primeiras = " ".join(admin_nome_completo.split()[:2])
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        new_file_name = f"{duas_primeiras}-EDITADO-{original_name}-{timestamp}.xlsx"
        s3_key = f"VR - DOCS/importacoes/editadas/{new_file_name}"

        s3.upload_fileobj(planilha_bytes, "fedcorp-prod", s3_key)

        s3_url = f"https://fedcorp-prod.s3.us-east-2.amazonaws.com/{quote(s3_key)}"

        file_upload.arquivo_s3_editado = s3_url
        file_upload.save(update_fields=['arquivo_s3_editado'])

        logger.info(f"Planilha editada salva em: {s3_url}")
        return s3_url

    except Exception as e:
        logger.error(f"Erro ao gerar/upload planilha editada: {traceback.format_exc()}")
        return None

class ConfirmationView(views.APIView):
    permission_classes = [IsAuthenticated] 
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        payload = request.data 
        logger.info(f"Recebido payload para confirmação: {payload}")
        
        file_id = payload.get("file_upload_id")
        importacao_id = payload.get("importacao_id")
        dados_modificados = payload.get("dados_modificados")

        if not file_id and not importacao_id:
            logger.warning("É obrigatório informar 'file_upload_id' ou 'importacao_id'.")
            return Response({"detail": "É obrigatório informar 'file_upload_id' ou 'importacao_id'."}, status=400)

        file_upload = None
        if file_id:
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
        
        serializer = ProcessamentoFinalSerializer(data=payload)
        
        if serializer.is_valid():
            try:
                result = serializer.save(processed_by=request.user)
                                       
                # Extrai dados do payload para o email
                summary = payload.get('summary', {})
                total_condominios = len(payload.get('condominios', []))
                total_funcionarios = summary.get('total_funcionarios', 0)
                total_movimentacoes = summary.get('total_movimentacoes', 0)
                
                # USA O VALOR TOTAL QUE FOI SALVO NA IMPORTAÇÃO
                importacao = Importacao.objects.get(id=result.get("importacao_id"))
                valor_total = float(importacao.valor_total)
                
                # Data de competência
                competencia_mes = payload.get('competencia_mes', '')
                competencia_ano = payload.get('competencia_ano', '')
                competencia_str = f"{competencia_mes}/{competencia_ano}" if competencia_mes and competencia_ano else "—"
                
                # Tipo de processamento
                tipo_processamento = payload.get('tipo_processamento', 'compra')
                tipo_display = "Compra de Benefícios" if tipo_processamento == "compra" else "Faturamento"
                
                # Nome do arquivo para exibição no email
                if file_upload and file_upload.file:
                    arquivo_nome = file_upload.file.name
                else:
                    arquivo_nome = "Faturamento_Repetido.xlsx" if importacao_id else "arquivo.xlsx"

                # Gerar planilha editada se dados_modificados foram enviados
                arquivo_s3_editado_url = None
                if dados_modificados and file_upload:
                    data_competencia = None
                    if competencia_mes and competencia_ano:
                        from datetime import datetime
                        try:
                            data_competencia = datetime(int(competencia_ano), int(competencia_mes), 1).date()
                        except Exception:
                            pass

                    arquivo_s3_editado_url = _gerar_e_upload_planilha_editada(
                        file_upload=file_upload,
                        dados_modificados=dados_modificados,
                        data_competencia=data_competencia,
                        request_user=request.user
                    )

                    # Atualizar Importacao com URL do arquivo editado
                    if arquivo_s3_editado_url:
                        importacao.arquivo_s3_editado = arquivo_s3_editado_url
                        importacao.save(update_fields=['arquivo_s3_editado'])

                logger.info(f"Dados para email - file_upload_id: {file_id}, total_condominios: {total_condominios}, total_funcionarios: {total_funcionarios}, total_movimentacoes: {total_movimentacoes}, valor_total: {valor_total}, competencia: {competencia_str}, tipo_processamento: {tipo_display}")

                fedhub_service = FedhubService()
                email_faturamento = settings.EMAIL_FATURAMENTO
                
                logger.info(f"Enviando email para {email_faturamento} com os dados do faturamento repetido/confirmado")
                
                # Envia email com dados REAIS
                email_enviado = fedhub_service.enviar_email_upload(
                    email=email_faturamento,
                    user=request.user,
                    dados_processamento={
                        "arquivo_nome": arquivo_nome,
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
                logger.info(f"Email de notificação enviado para {email_faturamento}: {email_enviado}")
                
                response_data = {
                    "detail": "Dados gravados com sucesso.",
                    "registros_processados": result.get("count"),
                    "importacao_id": result.get("importacao_id"),
                    "status": "AGUARDANDO_FATURAMENTO",
                    "email_enviado": email_enviado
                }

                if arquivo_s3_editado_url:
                    response_data["arquivo_s3_editado"] = arquivo_s3_editado_url

                if file_upload and file_upload.arquivo_s3:
                    response_data["arquivo_s3_original"] = file_upload.arquivo_s3

                return Response(response_data, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"Erro ao confirmar faturamento: {traceback.format_exc()}")
                if file_id:
                    FileUpload.objects.filter(id=file_id).update(process_status="FAILED")
                    Importacao.objects.filter(file_upload_id=file_id, status='AGUARDANDO_FATURAMENTO').update(status='FAILED')
                elif result and result.get("importacao_id"):
                    Importacao.objects.filter(id=result.get("importacao_id")).update(status='FAILED')
                return Response({"detail": f"Erro interno: {str(e)}"}, status=400) 

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)