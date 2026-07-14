import logging
import os
import math
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
import time

logger = logging.getLogger(__name__)

def sanitize_nan(obj):
    """Recursivamente substitui NaN, Infinity e -Infinity por None"""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_nan(item) for item in obj]
    return obj

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

            # Obtém os dados validados (movimentações)
            dados_validados = parsed_data.get("dados_validados", [])
            total_por_beneficiario = parsed_data.get("total_por_beneficiario", [])

            # 🔥 SANITIZAR dados_validados antes de tudo
            dados_validados = sanitize_nan(dados_validados)
            
            # Se não veio do parser, gera (fallback)
            if not total_por_beneficiario and dados_validados:
                from collections import defaultdict
                temp_map = defaultdict(lambda: {
                    "nome_funcionario": "",
                    "cpf": "",
                    "condominio": "",
                    "valor_total": 0.0,
                    "quantidade_dias": 0
                })
                for mov in dados_validados:
                    cpf = mov.get("cpf_funcionario", "")
                    if not cpf:
                        continue
                    valor = mov.get("valor_beneficio_total", 0)
                    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
                        valor = 0.0
                    dias = mov.get("quantidade_dias", 0)
                    if dias is None or (isinstance(dias, float) and math.isnan(dias)):
                        dias = 0
                    
                    temp_map[cpf]["nome_funcionario"] = mov.get("nome_funcionario", "")
                    temp_map[cpf]["cpf"] = cpf
                    temp_map[cpf]["condominio"] = mov.get("nome_condominio", "")
                    temp_map[cpf]["valor_total"] += float(valor)
                    temp_map[cpf]["quantidade_dias"] += int(dias)
                total_por_beneficiario = list(temp_map.values())

            # 🔥 SANITIZAR total_por_beneficiario
            total_por_beneficiario = sanitize_nan(total_por_beneficiario)

            # 🔥 Garantir que valor_total_vt não seja NaN
            valor_total_vt = parsed_data.get("valor_total_vt", 0)
            if valor_total_vt is None or (isinstance(valor_total_vt, float) and math.isnan(valor_total_vt)):
                valor_total_vt = 0.0

            # Cria o summary
            vt_summary = {
                "administradora_id": administradora_id or "",
                "total_condominios": parsed_data.get("total_condominios", 0),
                "total_funcionarios": parsed_data.get("total_funcionarios", 0),
                "total_movimentacoes": parsed_data.get("total_registros", 0),
                "valor_total_beneficios": float(valor_total_vt),
                "total_por_beneficiario": total_por_beneficiario,
                "total_registros": parsed_data.get("total_registros", 0),
                "total_dias_trabalhados": parsed_data.get("total_dias_trabalhados", 0),
                "valido": parsed_data.get("valido", False),
                "mensagem_validacao": parsed_data.get("mensagem_validacao", "Arquivo validado com sucesso"),
                "modelo_faturamento":"VT-AUTO" 
            }
            
            # 🔥 SANITIZAR summary
            vt_summary = sanitize_nan(vt_summary)
            
            logger.info(f"Summary gerado para VT: {vt_summary}")
            
            frontend_summary_safe = convert_decimals_to_json_safe(vt_summary)

            # Cria o data_to_backend
            data_to_backend = {
                "movimentacoes_detalhada": dados_validados,
                "summary": vt_summary,
                "file_upload_id": upload_instance.id
            }
            
            # 🔥 SANITIZAR data_to_backend
            data_to_backend = sanitize_nan(data_to_backend)
            data_to_backend_safe = convert_decimals_to_json_safe(data_to_backend)

            upload_instance.process_status = "PARSED"
            upload_instance.summary_data = frontend_summary_safe
            upload_instance.save()

            # Upload para S3
            if file_obj:
                original_name = file_obj.name.split('.')[0]
                user = request.user
                admin_nome_completo = str(user.administradora_ativa)
                duas_primeiras = " ".join(admin_nome_completo.split()[:2])
                ext = file_obj.name.split('.')[1]
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                
                new_file_name = f"{duas_primeiras}-VT-{original_name}-{timestamp}.{ext}"
                s3_key = f"VR - DOCS/importacoes_vt/{new_file_name}"
                
                file_obj.seek(0)
                s3.upload_fileobj(file_obj, "fedcorp-prod", s3_key)

                from urllib.parse import quote
                s3_url = f"https://fedcorp-prod.s3.us-east-2.amazonaws.com/{quote(s3_key)}"
                upload_instance.arquivo_s3 = s3_url
                upload_instance.save(update_fields=['arquivo_s3'])

            # Fecha o arquivo antes de tentar remover
            try:
                if hasattr(upload_instance.file, 'close'):
                    upload_instance.file.close()
            except:
                pass
            
            time.sleep(0.1)
            
            # Remove o arquivo local
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Arquivo removido com sucesso: {file_path}")
                except PermissionError as perm_err:
                    logger.warning(f"Não foi possível remover o arquivo {file_path}: {perm_err}")
                    time.sleep(1)
                    try:
                        os.remove(file_path)
                    except:
                        pass

            # 🔥 Garantir que a resposta não tenha NaN
            response_data = {
                "file_upload_id": upload_instance.id,
                "status": "PARSED",
                "summary": frontend_summary_safe,
                "data_to_backend": data_to_backend_safe,
                "movimentacoes_detalhada": dados_validados,
                "dados_validados": dados_validados,
                "linhas_com_erro": parsed_data.get("linhas_com_erro", []) or [],
                "detail": "Arquivo de Vale Transporte processado com sucesso."
            }
            
            # 🔥 Última sanitização
            response_data = sanitize_nan(response_data)
            
            return Response(
                response_data,
                status=status.HTTP_202_ACCEPTED,
            )
            
        except Exception as e:
            logger.error(f"Erro no processamento: {str(e)}", exc_info=True)
            try:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
            except:
                pass
            return self._handle_error(upload_instance, f"Erro inesperado: {str(e)}")

    def _get_beneficiary_summary(self, movimentacoes):
        """Agrupa movimentações por beneficiário (CPF)"""
        from collections import defaultdict
        import math
        
        summary_map = defaultdict(lambda: {
            "nome_funcionario": "",
            "cpf": "",
            "condominio": "",
            "valor_total": 0.0,
            "quantidade_dias": 0
        })
        
        for mov in movimentacoes:
            cpf = mov.get("cpf_funcionario", "")
            if not cpf:
                continue
                
            nome = mov.get("nome_funcionario", "")
            condominio = mov.get("nome_condominio", "")
            
            valor = mov.get("valor_beneficio_total", 0)
            if valor is None or (isinstance(valor, float) and math.isnan(valor)):
                valor = 0
            valor = float(valor)
            
            dias = mov.get("quantidade_dias", 0)
            if dias is None or (isinstance(dias, float) and math.isnan(dias)):
                dias = 0
            dias = int(dias)
            
            logger.info(f"Processando mov: cpf={cpf}, nome={nome}, valor={valor}, dias={dias}")
            
            summary_map[cpf]["nome_funcionario"] = nome
            summary_map[cpf]["cpf"] = cpf
            summary_map[cpf]["condominio"] = condominio
            summary_map[cpf]["valor_total"] += valor
            summary_map[cpf]["quantidade_dias"] += dias
        
        result = []
        for item in summary_map.values():
            result.append({
                "nome_funcionario": item["nome_funcionario"],
                "cpf": item["cpf"],
                "condominio": item["condominio"],
                "valor_total": float(item["valor_total"]),
                "quantidade_dias": item["quantidade_dias"]
            })
        
        logger.info(f"Beneficiary summary gerado: {result}")
        return result

    def _handle_error(self, instance, message):
        instance.process_status = "FAILED"
        instance.summary_data = {"error": message}
        instance.save()
        return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)