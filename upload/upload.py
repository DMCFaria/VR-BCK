import logging
import os
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import FileUploadSerializer
from .utils import convert_decimals_to_json_safe, get_beneficiary_summary, get_movimentacoes_detalhada
from datetime import datetime
import boto3   
from django.conf import settings

# Aqui você importará os parsers conforme sua estrutura de pastas
from decimal import Decimal
from .RB.parsers import parse_rb_layout
from .EXCEL.reader2 import parse_fut_template
from .AHREAS.parsers import parse_ahreas_layout
from .layout_detector import detect_txt_layout
from entidades.models import Administradora

logger = logging.getLogger(__name__)

class UploadView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):        
        # logger.info(f"Received upload request from user: {request.data.get('administradora_id')}")
        serializer = FileUploadSerializer(data=request.data)
        administradora_id = request.data.get('administradora_id')
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # 1. Registro inicial do upload
        upload_instance = serializer.save(
            uploaded_by=request.user, 
            process_status="PENDING"
        )
        
        file_path = upload_instance.file.path
        extension = os.path.splitext(file_path)[1].lower()
        file_type = request.POST.get('file_type', 'UNKNOWN')
        file_obj = request.FILES.get('file')

        s3 = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )
        
        # 2. Busca o valor máximo por funcionário da administradora
        valor_max = Decimal('9999.99')
        if administradora_id:
            try:
                adm = Administradora.objects.get(id=administradora_id)
                valor_max = adm.valor_max_beneficio
            except Administradora.DoesNotExist:
                pass

        try:
            # 3. Roteamento Dinâmico
            import_mode = None
            if extension == '.txt':
                import_mode = detect_txt_layout(file_path)
                logger.info(f"Detected TXT layout: {import_mode}")
                if import_mode == 'RB':
                    parsed_data = parse_rb_layout(file_path, upload_instance.id, valor_max_beneficio=valor_max)
                elif import_mode == 'AHREAS':
                    parsed_data = parse_ahreas_layout(file_path, upload_instance.id, valor_max_beneficio=valor_max)
                else:
                    return self._handle_error(upload_instance, f"Layout TXT '{import_mode}' não reconhecido.")
                logger.info(f"Parsed data: {parsed_data}")
            elif extension in ['.xlsx', '.xlsm']:
                import_mode = None
                parsed_data = parse_fut_template(file_path, upload_instance.id, valor_max_beneficio=valor_max)
                logger.info(f"Parsed data (FUT): {parsed_data}")
            
            else:
                return self._handle_error(upload_instance, f"Extensão {extension} não permitida.")

            # 3. Verificação de erros internos do parser
            if "error" in parsed_data:
                return self._handle_error(upload_instance, parsed_data["error"])

            # 4. Processamento de Sumários (Reutilizando sua lógica original)
            beneficiary_summary = get_beneficiary_summary(parsed_data)
            
            # logger.info(f"Beneficiary summary: {beneficiary_summary}")
             
            frontend_summary = {
                "administradora_id": administradora_id,
                "total_condominios": parsed_data.get("summary", {}).get("total_condominios", 0),
                "total_funcionarios": parsed_data.get("summary", {}).get("total_funcionarios", 0),
                "total_movimentacoes": parsed_data.get("summary", {}).get("total_movimentacoes", 0),
                "valor_total_beneficios": parsed_data.get("summary", {}).get("valor_total_beneficios", 0),
                "data_competencia_arquivo": parsed_data.get("summary", {}).get("data_competencia_arquivo"),
                "total_por_beneficiario": beneficiary_summary,
                "novos_registros": parsed_data.get("novos_registros", {})
            }
            
            logger.info(f"Frontend summary before sanitization: {frontend_summary}")
            
            
            # frontend_summary_safe = convert_decimals_to_json_safe(frontend_summary)

            # movimentacoes_detalhada = get_movimentacoes_detalhada(parsed_data)

            # data_to_backend_safe = convert_decimals_to_json_safe({
            #     **parsed_data,
            #     "movimentacoes_detalhada": movimentacoes_detalhada,
            #     "file_upload_id": upload_instance.id
            # })

            # return Response(
            #     {
            #         "file_upload_id": upload_instance.id,
            #         "status": "PARSED",
            #         "summary": frontend_summary_safe,
            #         "data_to_backend": data_to_backend_safe,
            #         "movimentacoes_detalhada": movimentacoes_detalhada,
            #         "linhas_com_erro": parsed_data.get("linhas_com_erro", []),
            #         "detail": "Arquivo processado. Confirme os dados para gravação."
            #     },
            #     status=status.HTTP_202_ACCEPTED,
            # )           
            
            # logger.info(f"Frontend summary: {frontend_summary}")
            
            # 5. Sanitização e Resposta
            frontend_summary_safe = convert_decimals_to_json_safe(frontend_summary)
            
            movimentacoes_detalhada = get_movimentacoes_detalhada(parsed_data)
            
            # logger.info(f"Movimentações detalhadas: {movimentacoes_detalhada}")
            
            data_to_backend_safe = convert_decimals_to_json_safe({
                **parsed_data, 
                "movimentacoes_detalhada": movimentacoes_detalhada,
                "file_upload_id": upload_instance.id
            })
            
            # Verificar se há informações faltando ou linhas com erro
            erros_condominios = parsed_data.get("erros_condominios", [])
            linhas_com_erro = parsed_data.get("linhas_com_erro", [])
            
            tem_erros = len(erros_condominios) > 0 or len(linhas_com_erro) > 0
            
            if tem_erros:
                status_processamento = "ERRO"
                db_status = "FAILED"
                detail_msg = "Arquivo processado. Contudo, há informações ausentes na planilha ou nos condomínios."
            else:
                status_processamento = "PARSED"
                db_status = "PARSED"
                detail_msg = "Arquivo processado. Confirme os dados para gravação."
            
            upload_instance.process_status = db_status
            upload_instance.summary_data = frontend_summary_safe
            upload_instance.save()

            if file_obj:
                original_name = file_obj.name.split('.')[0]
                user = request.user
                admin_nome_completo = str(user.administradora_ativa)
                duas_primeiras = " ".join(admin_nome_completo.split()[:2])
                ext = file_obj.name.split('.')[1]
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                
                new_file_name = f"{duas_primeiras}-{file_type}-{original_name}-{timestamp}.{ext}"
                s3_key = f"VR - DOCS/importacoes/{new_file_name}"
                
                file_obj.seek(0)
                s3.upload_fileobj(file_obj, "fedcorp-prod", s3_key)

                from urllib.parse import quote
                s3_url = f"https://fedcorp-prod.s3.us-east-2.amazonaws.com/{quote(s3_key)}"
                upload_instance.arquivo_s3 = s3_url
                upload_instance.save(update_fields=['arquivo_s3'])

            # Remove o arquivo local do disco — já foi processado e está no S3
            if os.path.exists(file_path):
                os.remove(file_path)

            response_data = {
                "file_upload_id": upload_instance.id,
                "status": status_processamento,
                "summary": frontend_summary_safe,
                "data_to_backend": data_to_backend_safe,
                "linhas_com_erro": linhas_com_erro,
                "erros_condominios": erros_condominios,
                "detail": detail_msg,
            }
            if import_mode:
                response_data["importMode"] = import_mode

            return Response(
                response_data,
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            return self._handle_error(upload_instance, f"Erro inesperado: {str(e)}")

    def _handle_error(self, instance, message):
        """Helper para padronizar falhas"""
        instance.process_status = "FAILED"
        instance.summary_data = {"error": message}
        instance.save()
        return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)