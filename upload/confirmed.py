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
    """Baixa planilha original do S3, edita os dados e reupload como editada."""
    import boto3
    import tempfile
    import os
    from datetime import datetime
    from urllib.parse import quote, urlparse, unquote
    from .gerar_planilha_editada import editar_planilha_original
    from .utils import validar_extensao_arquivo

    tmp_path = None
    tmp_edit_path = None
    try:
        logger.info(f"[PLANILHA_EDITADA] Iniciando edição - file_upload_id: {file_upload.id}")
        logger.info(f"[PLANILHA_EDITADA] dados_modificados recebidos: {bool(dados_modificados)}")
        logger.info(f"[PLANILHA_EDITADA] data_competencia: {data_competencia}")

        if not dados_modificados:
            logger.warning("[PLANILHA_EDITADA] dados_modificados está vazio ou nulo")
            return None

        if not file_upload.arquivo_s3:
            logger.warning("[PLANILHA_EDITADA] arquivo_s3 não encontrado no file_upload")
            return None

        has_aws_key = bool(getattr(settings, 'ACCESS_KEY_S3', ''))
        has_aws_secret = bool(getattr(settings, 'SECRET_KEY_S3', ''))
        logger.debug(f"[PLANILHA_EDITADA] Credenciais AWS presentes - KEY: {has_aws_key}, SECRET: {has_aws_secret}")

        s3 = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )

        s3_url = file_upload.arquivo_s3
        parsed_url = urlparse(s3_url)
        s3_key_original = unquote(parsed_url.path.lstrip('/'))
        bucket_name = parsed_url.netloc.split('.')[0]

        logger.info(f"[PLANILHA_EDITADA] Baixando arquivo original do S3 - bucket: {bucket_name}, key: {s3_key_original}")

        original_ext = os.path.splitext(s3_key_original)[1] or '.xlsm'
        logger.debug(f"[PLANILHA_EDITADA] Extensão original detectada: '{original_ext}'")

        with tempfile.NamedTemporaryFile(suffix=original_ext, delete=False) as tmp:
            tmp_path = tmp.name
            s3.download_file(bucket_name, s3_key_original, tmp_path)

        downloaded_size = os.path.getsize(tmp_path)
        logger.info(f"[PLANILHA_EDITADA] Arquivo original baixado para: {tmp_path} - tamanho: {downloaded_size} bytes")

        logger.info(f"[PLANILHA_EDITADA] Iniciando edição da planilha original")
        planilha_bytes = editar_planilha_original(tmp_path, dados_modificados, data_competencia)

        if not planilha_bytes:
            logger.error("[PLANILHA_EDITADA] editar_planilha_original retornou None")
            return None

        edited_size = planilha_bytes.getbuffer().nbytes
        logger.info(f"[PLANILHA_EDITADA] Planilha editada com sucesso - tamanho: {edited_size} bytes")

        original_name = file_upload.file.name.split('.')[0] if file_upload.file else 'importacao'
        user = request_user
        admin_nome_completo = str(user.administradora_ativa) if user.administradora_ativa else 'SISTEMA'
        duas_primeiras = " ".join(admin_nome_completo.split()[:2])
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        base_name = f"{duas_primeiras}-EDITADO-{original_name}-{timestamp}"
        candidate_name = f"{base_name}{original_ext}"
        logger.debug(f"[PLANILHA_EDITADA] Nome candidato gerado: {candidate_name}")

        # Valida extensão do arquivo editado antes do upload para S3,
        # garantindo que nunca seja salvo sem extensão ou com extensão não permitida.
        with tempfile.NamedTemporaryFile(suffix=original_ext, delete=False) as tmp_edit:
            tmp_edit_path = tmp_edit.name
            planilha_bytes.seek(0)
            tmp_edit.write(planilha_bytes.read())

        new_file_name = validar_extensao_arquivo(tmp_edit_path, candidate_name)
        logger.debug(f"[PLANILHA_EDITADA] Nome validado para upload: {new_file_name}")

        s3_key_editado = f"VR - DOCS/importacoes/editadas/{new_file_name}"

        logger.info(f"[PLANILHA_EDITADA] Fazendo upload para S3 - bucket: fedcorp-prod, key: {s3_key_editado}")

        planilha_bytes.seek(0)
        s3.upload_fileobj(planilha_bytes, "fedcorp-prod", s3_key_editado)

        s3_url_editado = f"https://fedcorp-prod.s3.us-east-2.amazonaws.com/{quote(s3_key_editado)}"
        logger.info(f"[PLANILHA_EDITADA] Upload concluído - URL: {s3_url_editado}")

        file_upload.arquivo_s3_editado = s3_url_editado
        file_upload.save(update_fields=['arquivo_s3_editado'])
        logger.info(f"[PLANILHA_EDITADA] URL salva no banco de dados - file_upload_id: {file_upload.id}")

        return s3_url_editado

    except Exception as e:
        logger.error(f"[PLANILHA_EDITADA] Erro ao editar/upload planilha: {str(e)}")
        logger.error(f"[PLANILHA_EDITADA] Traceback: {traceback.format_exc()}")
        return None

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                logger.info(f"[PLANILHA_EDITADA] Arquivo temporário removido: {tmp_path}")
            except Exception:
                pass
        if tmp_edit_path and os.path.exists(tmp_edit_path):
            try:
                os.remove(tmp_edit_path)
                logger.info(f"[PLANILHA_EDITADA] Arquivo temporário editado removido: {tmp_edit_path}")
            except Exception:
                pass

class ConfirmationView(views.APIView):
    permission_classes = [IsAuthenticated] 
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        payload = request.data
        user = request.user
        logger.info(f"[CONFIRMACAO] Iniciando POST /confirm/ - user: {user}")
        logger.debug(f"[CONFIRMACAO] Payload completo: {payload}")

        file_id = payload.get("file_upload_id")
        importacao_id = payload.get("importacao_id")
        dados_modificados = payload.get("dados_modificados")
        condominios_data = payload.get("condominios")
        summary = payload.get('summary', {})

        logger.info(f"[CONFIRMACAO] file_upload_id: {file_id}, importacao_id: {importacao_id}")
        logger.debug(f"[CONFIRMACAO] dados_modificados presente: {bool(dados_modificados)}, condominios presente: {bool(condominios_data)}")
        logger.debug(f"[CONFIRMACAO] summary recebido: {summary}")

        if not file_id and not importacao_id:
            logger.warning("[CONFIRMACAO] É obrigatório informar 'file_upload_id' ou 'importacao_id'.")
            return Response({"detail": "É obrigatório informar 'file_upload_id' ou 'importacao_id'."}, status=400)

        file_upload = None
        if file_id:
            try:
                file_upload = FileUpload.objects.get(id=file_id)
                logger.info(f"[CONFIRMACAO] FileUpload encontrado - id: {file_id}, status: {file_upload.process_status}, arquivo_s3: {file_upload.arquivo_s3}")
                if file_upload.process_status == "COMPLETED":
                    logger.warning(f"[CONFIRMACAO] Arquivo {file_id} já foi processado anteriormente.")
                    return Response(
                        {"detail": "Este arquivo já foi processado anteriormente."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except FileUpload.DoesNotExist:
                logger.warning(f"[CONFIRMACAO] Arquivo {file_id} não encontrado.")
                return Response({"detail": "Arquivo não encontrado."}, status=404)

        logger.info("[CONFIRMACAO] Validando payload com ProcessamentoFinalSerializer")
        serializer = ProcessamentoFinalSerializer(data=payload)

        if serializer.is_valid():
            logger.info("[CONFIRMACAO] Payload válido. Iniciando salvamento dos dados.")
            try:
                result = serializer.save(processed_by=request.user)
                logger.info(f"[CONFIRMACAO] Dados salvos com sucesso - result: {result}")

                # Se o modo for cartão admin, dispara pesquisa assíncrona dos CNPJs.
                if result.get("cartao_admin"):
                    try:
                        from upload.tasks import pesquisar_enderecos_condominios
                        cnpjs_condominios = [
                            c.get("cnpj") for c in payload.get("condominios", []) if c.get("cnpj")
                        ]
                        if cnpjs_condominios:
                            pesquisar_enderecos_condominios.delay(
                                cnpjs=cnpjs_condominios,
                                importacao_id=result.get("importacao_id"),
                            )
                            logger.info(
                                f"[CONFIRMACAO] Pesquisa de endereços disparada para "
                                f"{len(cnpjs_condominios)} condomínios (cartão admin)."
                            )
                    except Exception as e:
                        logger.exception(
                            f"[CONFIRMACAO] Erro ao disparar pesquisa de endereços: {e}"
                        )

                # Extrai dados do payload para o email
                total_condominios = len(payload.get('condominios', []))
                total_funcionarios = summary.get('total_funcionarios', 0)
                total_movimentacoes = summary.get('total_movimentacoes', 0)
                logger.debug(f"[CONFIRMACAO] Totais do payload - condominios: {total_condominios}, funcionarios: {total_funcionarios}, movimentacoes: {total_movimentacoes}")

                # USA O VALOR TOTAL QUE FOI SALVO NA IMPORTAÇÃO
                importacao = Importacao.objects.get(id=result.get("importacao_id"))
                valor_total = float(importacao.valor_total)
                logger.info(f"[CONFIRMACAO] Importacao carregada - id: {importacao.id}, valor_total: {valor_total}, status: {importacao.status}")

                # Data de competência
                competencia_mes = payload.get('competencia_mes', '')
                competencia_ano = payload.get('competencia_ano', '')
                competencia_str = f"{competencia_mes}/{competencia_ano}" if competencia_mes and competencia_ano else "—"
                logger.debug(f"[CONFIRMACAO] Competência parseada: {competencia_str}")

                # Tipo de processamento
                tipo_processamento = payload.get('tipo_processamento', 'compra')
                tipo_display = "Compra de Benefícios" if tipo_processamento == "compra" else "Faturamento"
                logger.debug(f"[CONFIRMACAO] Tipo de processamento: {tipo_processamento} ({tipo_display})")

                # Nome do arquivo para exibição no email
                if file_upload and file_upload.file:
                    arquivo_nome = file_upload.file.name
                else:
                    arquivo_nome = "Faturamento_Repetido.xlsx" if importacao_id else "arquivo.xlsx"
                logger.debug(f"[CONFIRMACAO] Nome do arquivo para email: {arquivo_nome}")

                # Gerar planilha editada se dados_modificados foram enviados
                arquivo_s3_editado_url = None
                logger.info(f"[CONFIRMACAO] Verificando geração de planilha editada - dados_modificados: {bool(dados_modificados)}, file_upload: {bool(file_upload)}")

                if not dados_modificados and condominios_data:
                    dados_modificados = {"condominios": condominios_data}
                    logger.info("[CONFIRMACAO] dados_modificados não enviado, usando condominios como fallback")

                if dados_modificados and file_upload:
                    logger.info(f"[CONFIRMACAO] Iniciando geração de planilha editada")
                    data_competencia = None
                    if competencia_mes and competencia_ano:
                        from datetime import datetime
                        try:
                            data_competencia = datetime(int(competencia_ano), int(competencia_mes), 1).date()
                            logger.info(f"[CONFIRMACAO] Data de competência parseada: {data_competencia}")
                        except Exception as e:
                            logger.warning(f"[CONFIRMACAO] Erro ao parsear data de competência: {e}")

                    arquivo_s3_editado_url = _gerar_e_upload_planilha_editada(
                        file_upload=file_upload,
                        dados_modificados=dados_modificados,
                        data_competencia=data_competencia,
                        request_user=request.user
                    )
                    logger.info(f"[CONFIRMACAO] URL da planilha editada retornada: {arquivo_s3_editado_url}")

                    # Atualizar Importacao com URL do arquivo editado
                    if arquivo_s3_editado_url:
                        importacao.arquivo_s3_editado = arquivo_s3_editado_url
                        importacao.save(update_fields=['arquivo_s3_editado'])
                        logger.info(f"[CONFIRMACAO] URL da planilha editada salva na Importacao - id: {importacao.id}")
                    else:
                        logger.warning(f"[CONFIRMACAO] URL da planilha editada é None. Importacao não será atualizada com arquivo_s3_editado.")

                logger.info(f"[CONFIRMACAO] Dados para email - file_upload_id: {file_id}, total_condominios: {total_condominios}, total_funcionarios: {total_funcionarios}, total_movimentacoes: {total_movimentacoes}, valor_total: {valor_total}, competencia: {competencia_str}, tipo_processamento: {tipo_display}")

                fedhub_service = FedhubService()
                email_faturamento = settings.EMAIL_FATURAMENTO

                logger.info(f"[CONFIRMACAO] Enviando email para {email_faturamento}")

                # Envia email com dados REAIS
                email_payload = {
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
                logger.debug(f"[CONFIRMACAO] Payload do email: {email_payload}")

                email_enviado = fedhub_service.enviar_email_upload(
                    email=email_faturamento,
                    user=request.user,
                    dados_processamento=email_payload
                )
                logger.info(f"[CONFIRMACAO] Email de notificação enviado para {email_faturamento}: {email_enviado}")

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

                logger.info(f"[CONFIRMACAO] Resposta final: {response_data}")
                return Response(response_data, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"[CONFIRMACAO] Erro ao confirmar faturamento: {traceback.format_exc()}")
                if file_id:
                    FileUpload.objects.filter(id=file_id).update(process_status="FAILED")
                    Importacao.objects.filter(file_upload_id=file_id, status='AGUARDANDO_FATURAMENTO').update(status='FAILED')
                    logger.warning(f"[CONFIRMACAO] Status atualizado para FAILED - file_upload_id: {file_id}")
                elif result and result.get("importacao_id"):
                    Importacao.objects.filter(id=result.get("importacao_id")).update(status='FAILED')
                    logger.warning(f"[CONFIRMACAO] Status atualizado para FAILED - importacao_id: {result.get('importacao_id')}")
                return Response({"detail": f"Erro interno: {str(e)}"}, status=400)

        logger.warning(f"[CONFIRMACAO] Payload inválido - erros: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
