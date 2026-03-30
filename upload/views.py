import decimal
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.authentication import JWTAuthentication
from collections import defaultdict

# Importa o Parser
from .parsers import parse_rb_layout
from .serializers import ProcessamentoFinalSerializer, FileUploadSerializer
from .models import FileUpload


# --- FUNÇÕES AUXILIARES ---

def _convert_decimals_to_json_safe(data):
    """
    Recursivamente converte objetos Decimal para strings para serialização JSON.
    Funciona para dicionários, listas e valores isolados.
    """
    if isinstance(data, dict):
        return {key: _convert_decimals_to_json_safe(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_convert_decimals_to_json_safe(element) for element in data]
    elif isinstance(data, decimal.Decimal):
        return str(data) 
    return data

def _get_beneficiary_summary(parsed_data):
    """
    Calcula o total de benefícios por funcionário a partir da lista detalhada (planilha).
    """
    movimentacoes_detalhada = parsed_data.get('movimentacoes_detalhada', [])
    total_por_cpf = defaultdict(decimal.Decimal)
    nomes_por_cpf = {}
    departamentos_por_cpf = {}

    for row in movimentacoes_detalhada:
        cpf = row.get('cpf_func')
        nome = row.get('nome_func')
        valor = row.get('valor_recarga_bene')
        condominio = row.get('departamento')

        if cpf and valor is not None:
            if not isinstance(valor, decimal.Decimal):
                try: 
                    valor = decimal.Decimal(str(valor))
                except: 
                    valor = decimal.Decimal('0.00')
            total_por_cpf[cpf] += valor
            nomes_por_cpf[cpf] = nome
            departamentos_por_cpf[cpf] = condominio

    summary_list = []
    for cpf, total in total_por_cpf.items():
        summary_list.append({
            "nome_funcionario": nomes_por_cpf.get(cpf, "Nome não encontrado"),
            "cpf": cpf,
            "valor_total": str(total), # Já converte para string aqui por segurança
            "condominio": departamentos_por_cpf.get(cpf)
        })
    return summary_list


# --- VIEWS ---

class UploadView(views.APIView):
    """
    Endpoint para fazer o upload do arquivo e realizar o parsing inicial.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):
        serializer = FileUploadSerializer(data=request.data)
        if serializer.is_valid():
            
            upload_instance = serializer.save(
                uploaded_by=request.user, 
                process_status="PENDING"
            )
            
            file_path = upload_instance.file.path
            parsed_data = parse_rb_layout(file_path, upload_instance.id)

            if "error" in parsed_data:
                upload_instance.process_status = "FAILED"
                error_msg = {"error": parsed_data["error"]}
                upload_instance.summary_data = error_msg
                upload_instance.save()
                return Response(
                    {"detail": f"Falha no parsing: {parsed_data['error']}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Extração e Limpeza dos dados
            raw_summary = parsed_data.get("summary", {})
            beneficiary_summary = _get_beneficiary_summary(parsed_data)
            novos_registros = parsed_data.get("novos_registros", {})

            frontend_summary = {
                "total_condominios": raw_summary.get("total_condominios", 0),
                "total_funcionarios": raw_summary.get("total_funcionarios", 0),
                "total_movimentacoes": raw_summary.get("total_movimentacoes", 0),
                "valor_total_beneficios": raw_summary.get("valor_total_beneficios", 0),
                "data_competencia_arquivo": raw_summary.get("data_competencia_arquivo"),
                "total_por_beneficiario": beneficiary_summary,
                "novos_registros": novos_registros 
            }
            
            # Sanitização crucial antes de salvar no banco ou enviar na Response
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

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ConfirmationView(views.APIView):
    permission_classes = [IsAuthenticated] 
    authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):
        payload = request.data # Removido .copy() se não houver mutação manual necessária
        file_id = payload.get("file_upload_id")

        if not file_id:
            return Response({"detail": "O campo 'file_upload_id' é obrigatório."}, status=400)

        # O Serializer agora fará a transação atômica e o lock do registro
        serializer = ProcessamentoFinalSerializer(data=payload)

        if serializer.is_valid():
            try:
                # Passamos o usuário logado para o save
                result = serializer.save(processed_by=request.user)
                
                return Response(
                    {
                        "detail": "Dados gravados com sucesso.",
                        "registros_processados": result.get("count"),
                        "status": "COMPLETED"
                    },
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                 # Caso ocorra erro, o status é gerido aqui ou dentro do Serializer
                 FileUpload.objects.filter(id=file_id).update(process_status="FAILED")
                 return Response({"detail": f"Erro interno ao gravar: {str(e)}"}, status=500)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)