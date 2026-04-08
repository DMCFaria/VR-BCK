import os
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import FileUploadSerializer
from .utils import _get_beneficiary_summary, _convert_decimals_to_json_safe



# Aqui você importará os parsers conforme sua estrutura de pastas
from .RB.parsers import parse_rb_layout
# from .excel.parsers import parse_excel_layout

class UploadView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):
        serializer = FileUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # 1. Registro inicial do upload
        upload_instance = serializer.save(
            uploaded_by=request.user, 
            process_status="PENDING"
        )
        
        file_path = upload_instance.file.path
        extension = os.path.splitext(file_path)[1].lower()

        try:
            # 2. Roteamento Dinâmico
            if extension == '.txt':
                # Executa o seu parser RB original
                parsed_data = parse_rb_layout(file_path, upload_instance.id)
            
            elif extension in ['.xlsx', '.xls', '.csv']:
                # Quando o diretor decidir o modelo, implementamos aqui
                return self._handle_error(upload_instance, "Parser de Excel/CSV ainda não configurado.")
            
            else:
                return self._handle_error(upload_instance, f"Extensão {extension} não permitida.")

            # 3. Verificação de erros internos do parser
            if "error" in parsed_data:
                return self._handle_error(upload_instance, parsed_data["error"])

            # 4. Processamento de Sumários (Reutilizando sua lógica original)
            beneficiary_summary = _get_beneficiary_summary(parsed_data)
            
            frontend_summary = {
                "total_condominios": parsed_data.get("summary", {}).get("total_condominios", 0),
                "total_funcionarios": parsed_data.get("summary", {}).get("total_funcionarios", 0),
                "total_movimentacoes": parsed_data.get("summary", {}).get("total_movimentacoes", 0),
                "valor_total_beneficios": parsed_data.get("summary", {}).get("valor_total_beneficios", 0),
                "data_competencia_arquivo": parsed_data.get("summary", {}).get("data_competencia_arquivo"),
                "total_por_beneficiario": beneficiary_summary,
                "novos_registros": parsed_data.get("novos_registros", {})
            }
            
            # 5. Sanitização e Resposta
            frontend_summary_safe = _convert_decimals_to_json_safe(frontend_summary)
            data_to_backend_safe = _convert_decimals_to_json_safe({
                **parsed_data, 
                "file_upload_id": upload_instance.id
            })
            
            upload_instance.process_status = "PARSED"
            upload_instance.summary_data = frontend_summary_safe
            upload_instance.save()

            return Response(
                {
                    "file_upload_id": upload_instance.id,
                    "status": "PARSED",
                    "summary": frontend_summary_safe,
                    "data_to_backend": data_to_backend_safe,
                    "detail": "Arquivo processado. Confirme os dados para gravação."
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception as e:
            return self._handle_error(upload_instance, f"Erro inesperado: {str(e)}")

    def _handle_error(self, instance, message):
        """Helper para padronizar falhas"""
        instance.process_status = "FAILED"
        instance.summary_data = {"error": message}
        instance.save()
        return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)