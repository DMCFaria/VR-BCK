import logging
from collections import defaultdict

from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.fedhub.services.fedhub_service import FedhubService
from .serializers import ProcessamentoFinalSerializer
from .models import FileUpload
from .utils import validar_extensao_arquivo
from .gerar_planilha_editada import editar_planilha_vt
from beneficios.models import Importacao
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


def _gerar_e_upload_planilha_editada_vt(file_upload, condominios, data_competencia, request_user):
    """Baixa planilha VT original do S3, edita os dados e reupload como editada."""
    import boto3
    import tempfile
    import os
    from datetime import datetime
    from urllib.parse import quote, urlparse, unquote

    tmp_path = None
    tmp_edit_path = None
    try:
        logger.info(f"[PLANILHA_EDITADA_VT] Iniciando edição - file_upload_id: {file_upload.id}")

        if not file_upload.arquivo_s3:
            logger.warning("[PLANILHA_EDITADA_VT] arquivo_s3 não encontrado no file_upload")
            return None

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

        logger.info(f"[PLANILHA_EDITADA_VT] Baixando arquivo original do S3 - bucket: {bucket_name}, key: {s3_key_original}")

        original_ext = os.path.splitext(s3_key_original)[1] or '.xlsm'
        with tempfile.NamedTemporaryFile(suffix=original_ext, delete=False) as tmp:
            tmp_path = tmp.name
            s3.download_file(bucket_name, s3_key_original, tmp_path)

        downloaded_size = os.path.getsize(tmp_path)
        logger.info(f"[PLANILHA_EDITADA_VT] Arquivo original baixado para: {tmp_path} - tamanho: {downloaded_size} bytes")

        dados_modificados = {"condominios": condominios}
        planilha_bytes = editar_planilha_vt(tmp_path, dados_modificados, data_competencia)

        if not planilha_bytes:
            logger.error("[PLANILHA_EDITADA_VT] editar_planilha_vt retornou None")
            return None

        edited_size = planilha_bytes.getbuffer().nbytes
        logger.info(f"[PLANILHA_EDITADA_VT] Planilha VT editada com sucesso - tamanho: {edited_size} bytes")

        original_name = file_upload.file.name.split('.')[0] if file_upload.file else 'importacao'
        user = request_user
        admin_nome_completo = str(user.administradora_ativa) if user.administradora_ativa else 'SISTEMA'
        duas_primeiras = " ".join(admin_nome_completo.split()[:2])
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        base_name = f"{duas_primeiras}-EDITADO-VT-{original_name}-{timestamp}"
        candidate_name = f"{base_name}{original_ext}"

        with tempfile.NamedTemporaryFile(suffix=original_ext, delete=False) as tmp_edit:
            tmp_edit_path = tmp_edit.name
            planilha_bytes.seek(0)
            tmp_edit.write(planilha_bytes.read())

        new_file_name = validar_extensao_arquivo(tmp_edit_path, candidate_name)
        s3_key_editado = f"VR - DOCS/importacoes_vt/editadas/{new_file_name}"

        logger.info(f"[PLANILHA_EDITADA_VT] Fazendo upload para S3 - bucket: fedcorp-prod, key: {s3_key_editado}")

        planilha_bytes.seek(0)
        s3.upload_fileobj(planilha_bytes, "fedcorp-prod", s3_key_editado)

        s3_url_editado = f"https://fedcorp-prod.s3.us-east-2.amazonaws.com/{quote(s3_key_editado)}"
        logger.info(f"[PLANILHA_EDITADA_VT] Upload concluído - URL: {s3_url_editado}")

        file_upload.arquivo_s3_editado = s3_url_editado
        file_upload.save(update_fields=['arquivo_s3_editado'])
        logger.info(f"[PLANILHA_EDITADA_VT] URL salva no banco de dados - file_upload_id: {file_upload.id}")

        return s3_url_editado

    except Exception as e:
        logger.error(f"[PLANILHA_EDITADA_VT] Erro ao editar/upload planilha VT: {str(e)}", exc_info=True)
        return None

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                logger.info(f"[PLANILHA_EDITADA_VT] Arquivo temporário removido: {tmp_path}")
            except Exception:
                pass
        if tmp_edit_path and os.path.exists(tmp_edit_path):
            try:
                os.remove(tmp_edit_path)
                logger.info(f"[PLANILHA_EDITADA_VT] Arquivo temporário editado removido: {tmp_edit_path}")
            except Exception:
                pass


class ConfirmVTView(views.APIView):
    permission_classes = [IsAuthenticated] 
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        payload = request.data
        logger.info(f"ConfirmVTView - Recebido payload: {payload}")

        file_id = payload.get("file_upload_id")

        if not file_id:
            return Response({"detail": "O campo 'file_upload_id' é obrigatório."}, status=400)

        try:
            file_upload = FileUpload.objects.get(id=file_id)
            if file_upload.process_status == "COMPLETED":
                return Response(
                    {"detail": "Este arquivo já foi processado anteriormente."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except FileUpload.DoesNotExist:
            return Response({"detail": "Arquivo não encontrado."}, status=404)

        dados_validados = payload.get("dados_validados") or payload.get("movimentacoes_detalhada") or []

        if not dados_validados:
            return Response({"detail": "Nenhum dado validado para processar."}, status=400)

        condominios = self._transform_to_condominios(dados_validados)

        errors_endereco = self._validar_enderecos_condominio(condominios)
        if errors_endereco:
            return Response({
                "detail": "Endereço do condomínio é obrigatório para importação VT.",
                "condominios_sem_endereco": errors_endereco
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer_payload = {
            "condominios": condominios,
            "file_upload_id": file_id,
            "summary": payload.get("summary", {}),
            "competencia_mes": payload.get("competencia_mes"),
            "competencia_ano": payload.get("competencia_ano"),
            "vencimento": payload.get("vencimento"),
            "data_vencimento": payload.get("data_vencimento"),
            "periodo_inicio": payload.get("periodo_inicio"),
            "periodo_fim": payload.get("periodo_fim"),
            "vigencia_inicio": payload.get("vigencia_inicio"),
            "vigencia_fim": payload.get("vigencia_fim"),
            "tipo_processamento": payload.get("tipo_processamento", "compra"),
            "modelo_importacao": "VT-AUTO",
        }

        serializer = ProcessamentoFinalSerializer(data=serializer_payload)

        if not serializer.is_valid():
            logger.error(f"Erros de validação: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = serializer.save(processed_by=request.user)

            summary = payload.get('summary', {})
            total_condominios = len(condominios)
            total_funcionarios = summary.get('total_funcionarios', 0)
            total_movimentacoes = summary.get('total_movimentacoes', 0)

            importacao = Importacao.objects.get(id=result.get("importacao_id"))
            valor_total = float(importacao.valor_total)

            competencia_mes = payload.get('competencia_mes', '')
            competencia_ano = payload.get('competencia_ano', '')
            competencia_str = f"{competencia_mes}/{competencia_ano}" if competencia_mes and competencia_ano else "—"

            tipo_processamento = payload.get('tipo_processamento', 'compra')
            tipo_display = "Compra de Benefícios" if tipo_processamento == "compra" else "Faturamento"

            # Gerar planilha VT editada
            arquivo_s3_editado_url = None
            if file_upload and file_upload.arquivo_s3:
                logger.info("[CONFIRMACAO_VT] Iniciando geração de planilha VT editada")
                data_competencia = None
                if competencia_mes and competencia_ano:
                    from datetime import datetime
                    try:
                        data_competencia = datetime(int(competencia_ano), int(competencia_mes), 1).date()
                    except Exception:
                        pass

                arquivo_s3_editado_url = _gerar_e_upload_planilha_editada_vt(
                    file_upload=file_upload,
                    condominios=condominios,
                    data_competencia=data_competencia,
                    request_user=request.user
                )
                logger.info(f"[CONFIRMACAO_VT] URL da planilha VT editada: {arquivo_s3_editado_url}")

                if arquivo_s3_editado_url:
                    importacao.arquivo_s3_editado = arquivo_s3_editado_url
                    importacao.save(update_fields=['arquivo_s3_editado'])
                    logger.info(f"[CONFIRMACAO_VT] URL da planilha VT editada salva na Importacao - id: {importacao.id}")
                else:
                    logger.warning("[CONFIRMACAO_VT] URL da planilha VT editada é None")

            fedhub_service = FedhubService()
            email_faturamento = settings.EMAIL_FATURAMENTO

            email_enviado = fedhub_service.enviar_email_upload(
                email=email_faturamento,
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

            response_data = {
                "detail": "Dados de Vale Transporte salvos com sucesso.",
                "registros_processados": result.get("count"),
                "importacao_id": result.get("importacao_id"),
                "status": "AGUARDANDO_FATURAMENTO",
                "email_enviado": email_enviado
            }

            if arquivo_s3_editado_url:
                response_data["arquivo_s3_editado"] = arquivo_s3_editado_url

            if file_upload and file_upload.arquivo_s3:
                response_data["arquivo_s3_original"] = file_upload.arquivo_s3

            logger.info(f"[CONFIRMACAO_VT] Resposta final: {response_data}")
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Erro ao processar VT: {str(e)}", exc_info=True)
            FileUpload.objects.filter(id=file_id).update(process_status="FAILED")
            Importacao.objects.filter(file_upload_id=file_id, status='AGUARDANDO_FATURAMENTO').update(status='FAILED')
            return Response({"detail": f"Erro interno: {str(e)}"}, status=400)

    def _transform_to_condominios(self, dados_validados):
        condominios_map = defaultdict(lambda: {
            "nome": "",
            "cnpj": "",
            "rua": "",
            "bairro": "",
            "cidade": "",
            "estado": "",
            "cep": "",
            "funcionarios_map": defaultdict(lambda: {
                "nome": "",
                "cpf": "",
                "matricula": "",
                "funcao": "",
                "endereco_rua": "",
                "endereco_numero": "",
                "endereco_complemento": "",
                "endereco_bairro": "",
                "cep": "",
                "data_nascimento": "",
                "movimentacoes": []
            })
        })

        for item in dados_validados:
            cnpj = item.get("cnpj_condominio", "")
            if not cnpj:
                continue

            condo = condominios_map[cnpj]
            condo["nome"] = item.get("nome_condominio", "")
            condo["cnpj"] = cnpj
            condo["rua"] = item.get("endereco_departamento", "")
            condo["bairro"] = item.get("bairro_departamento", "")
            condo["cidade"] = item.get("cidade_departamento", "")
            condo["estado"] = item.get("uf_departamento", "")
            condo["cep"] = item.get("cep_departamento", "")

            cpf = item.get("cpf_funcionario", "")
            if not cpf:
                continue

            func = condo["funcionarios_map"][cpf]
            func["nome"] = item.get("nome_funcionario", "")
            func["cpf"] = cpf
            func["matricula"] = item.get("matricula_funcionario", "")
            func["funcao"] = item.get("funcao_funcionario", "")
            func["endereco_rua"] = item.get("logradouro", "")
            func["endereco_numero"] = item.get("numero", "")
            func["endereco_complemento"] = item.get("complemento", "")
            func["endereco_bairro"] = item.get("bairro", "")
            func["cep"] = item.get("cep", "")
            func["data_nascimento"] = item.get("data_nascimento", "")

            func["movimentacoes"].append({
                "produto": item.get("nome_produto", "Vale Transporte"),
                "codigo_produto": item.get("codigo_produto", "VT"),
                "valor": float(item.get("valor_beneficio_total", 0)),
                "quantidade": int(item.get("quantidade", 1)),
                "quantidade_dias": int(item.get("quantidade_dias", 0))
            })

        result = []
        for cnpj, condo in condominios_map.items():
            funcionarios = []
            for cpf, func in condo["funcionarios_map"].items():
                funcionarios.append({
                    "nome": func["nome"],
                    "cpf": func["cpf"],
                    "matricula": func["matricula"],
                    "funcao": func["funcao"],
                    "endereco_rua": func["endereco_rua"],
                    "endereco_numero": func["endereco_numero"],
                    "endereco_complemento": func["endereco_complemento"],
                    "endereco_bairro": func["endereco_bairro"],
                    "cep": func["cep"],
                    "data_nascimento": func["data_nascimento"],
                    "movimentacoes": func["movimentacoes"]
                })
            result.append({
                "nome": condo["nome"],
                "cnpj": condo["cnpj"],
                "rua": condo["rua"],
                "bairro": condo["bairro"],
                "cidade": condo["cidade"],
                "estado": condo["estado"],
                "cep": condo["cep"],
                "funcionarios": funcionarios
            })

        return result

    def _validar_enderecos_condominio(self, condominios):
        errors = []
        for condo in condominios:
            nome = condo.get("nome", "")
            cnpj = condo.get("cnpj", "")
            if not condo.get("rua") or not condo.get("cidade") or not condo.get("estado"):
                errors.append({
                    "nome": nome,
                    "cnpj": cnpj,
                    "campos_faltantes": []
                })
                if not condo.get("rua"):
                    errors[-1]["campos_faltantes"].append("endereco_departamento")
                if not condo.get("cidade"):
                    errors[-1]["campos_faltantes"].append("cidade_departamento")
                if not condo.get("estado"):
                    errors[-1]["campos_faltantes"].append("uf_departamento")
        return errors
