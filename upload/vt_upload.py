import logging
import os
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from upload.vt_parser import parse_vt_excel
from .serializers import FileUploadSerializer
from .utils import convert_decimals_to_json_safe
from datetime import datetime
import boto3   
from django.conf import settings

logger = logging.getLogger(__name__)

class UploadVTView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):
        serializer = FileUploadSerializer(data=request.data)
        administradora_id = request.data.get('administradora_id')
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        upload_instance = serializer.save(
            uploaded_by=request.user, 
            process_status="PENDING"
        )
        
        file_path = upload_instance.file.path
        extension = os.path.splitext(file_path)[1].lower()
        file_obj = request.FILES.get('file')

        s3 = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )
        
        try:
            if extension not in ['.xlsx', '.xls', '.csv']:
                return self._handle_error(upload_instance, f"Extensão {extension} não permitida para VT.")

            # Parse específico para VT
            parsed_data = parse_vt_excel(file_path, upload_instance.id)
            
            if "error" in parsed_data:
                return self._handle_error(upload_instance, parsed_data["error"])

            # Gera summary específico para VT (apenas validação, sem beneficiários)
            vt_summary = {
                "administradora_id": administradora_id,
                "total_registros": parsed_data.get("total_registros", 0),
                "total_funcionarios": parsed_data.get("total_funcionarios", 0),
                "total_condominios": parsed_data.get("total_condominios", 0),
                "valor_total_vt": parsed_data.get("valor_total_vt", 0),
                "total_dias_trabalhados": parsed_data.get("total_dias_trabalhados", 0),
                "valido": parsed_data.get("valido", False),
                "mensagem_validacao": parsed_data.get("mensagem_validacao", "Arquivo validado com sucesso")
            }
            
            logger.info(f"Summary gerado para VT: {vt_summary}")
            
            frontend_summary_safe = convert_decimals_to_json_safe(vt_summary)

            upload_instance.process_status = "PARSED"
            upload_instance.summary_data = frontend_summary_safe
            upload_instance.save()

            if file_obj:
                original_name = file_obj.name.split('.')[0]
                user = request.user
                admin_nome_completo = str(user.administradora)
                duas_primeiras = " ".join(admin_nome_completo.split()[:2])
                ext = file_obj.name.split('.')[1]
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                
                new_file_name = f"{duas_primeiras}-VT-{original_name}-{timestamp}.{ext}"
                
                file_obj.seek(0)
                s3.upload_fileobj(file_obj, "fedcorp-prod", f"VR - DOCS/importacoes_vt/{new_file_name}")

            if os.path.exists(file_path):
                os.remove(file_path)

            # Retorna os dados validados (apenas validação, sem processamento de benefícios)
            return Response(
                {
                    "file_upload_id": upload_instance.id,
                    "status": "VALIDATED",
                    "summary": frontend_summary_safe,
                    "dados_validados": parsed_data.get("dados_validados", []),
                    "linhas_com_erro": parsed_data.get("linhas_com_erro", []),
                    "detail": "Arquivo de Vale Transporte validado com sucesso. Nenhum benefício foi processado."
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            return self._handle_error(upload_instance, f"Erro inesperado: {str(e)}")

    def _handle_error(self, instance, message):
        instance.process_status = "FAILED"
        instance.summary_data = {"error": message}
        instance.save()
        return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)