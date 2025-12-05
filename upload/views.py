import decimal
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from collections import defaultdict

# Importa o Parser
from .parsers import parse_rb_layout
from .serializers import ProcessamentoFinalSerializer, FileUploadSerializer
from .models import FileUpload


# --- FUNÇÕES AUXILIARES ---

def _convert_decimals_to_json_safe(data):
    """
    Recursivamente converte objetos Decimal para strings para serialização JSON.
    """
    if isinstance(data, dict):
        # Percorre o dicionário
        return {
            key: _convert_decimals_to_json_safe(value) 
            for key, value in data.items()
        }
    elif isinstance(data, list):
        # Percorre a lista
        return [
            _convert_decimals_to_json_safe(element) 
            for element in data
        ]
    elif isinstance(data, decimal.Decimal):
        # CONVERSÃO PRINCIPAL: Decimal para string
        return str(data) 
    
    # Se for outro tipo, retorna o valor inalterado
    return data

def _get_beneficiary_summary(parsed_data):
    """
    Calcula o total de benefícios por funcionário a partir da lista detalhada (planilha).
    """
    movimentacoes_detalhada = parsed_data.get('movimentacoes_detalhada', [])
    total_por_cpf = defaultdict(decimal.Decimal)
    nomes_por_cpf = {}

    for row in movimentacoes_detalhada:
        cpf = row.get('cpf_func')
        nome = row.get('nome_func')
        valor = row.get('valor_recarga_bene')
        condominio = row.get('departamento')

        if cpf and valor is not None:
            if not isinstance(valor, decimal.Decimal):
                try: valor = decimal.Decimal(str(valor))
                except: valor = decimal.Decimal(0)
            total_por_cpf[cpf] += valor
            nomes_por_cpf[cpf] = nome

    summary_list = []
    for cpf, total in total_por_cpf.items():
        summary_list.append({
            "nome_funcionario": nomes_por_cpf.get(cpf, "Nome não encontrado"),
            "cpf": cpf,
            "valor_total": total,
            "condominio": condominio
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
                upload_instance.summary_data = _convert_decimals_to_json_safe(error_msg)
                upload_instance.save()
                return Response(
                    {"detail": f"Falha no parsing: {parsed_data['error']}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

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
            
            data_to_backend = {
                **parsed_data, 
                "file_upload_id": upload_instance.id
            }
            
            upload_instance.process_status = "PARSED"
            upload_instance.summary_data = _convert_decimals_to_json_safe(frontend_summary)
            upload_instance.save()

            return Response(
                {
                    "file_upload_id": upload_instance.id,
                    "status": "PARSED",
                    "summary": _convert_decimals_to_json_safe(frontend_summary),
                    "data_to_backend": _convert_decimals_to_json_safe(data_to_backend),
                    "detail": "Arquivo processado. Confirme os dados para gravação."
                },
                status=status.HTTP_202_ACCEPTED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    

def _convert_decimals_to_json_safe(data):
    # Sua implementação original...
    return data 

class ConfirmationView(views.APIView):
    """
    Endpoint para confirmar a persistência.
    """
    permission_classes = [IsAuthenticated] 

    def post(self, request, *args, **kwargs):
        # Usamos .copy() para garantir que podemos modificar o dicionário, se necessário, 
        # antes de passá-lo para a função de conversão ou serializer, embora o código original não modifique.
        payload = request.data.copy()
        file_id = payload.get("file_upload_id") # Não removemos o file_id do payload

        if not file_id:
            return Response({"detail": "O campo 'file_upload_id' é obrigatório."}, status=400)

        # Usamos o file_id para buscar a instância do FileUpload
        upload_instance = get_object_or_404(FileUpload, id=file_id)
        
        # Evita processar arquivo já finalizado
        if upload_instance.process_status == "COMPLETED":
             return Response({"detail": "Este arquivo já foi processado."}, status=400)

        # 1. Torna o payload seguro para JSON, convertendo Decimais, etc.
        # O payload_safe contém TODOS os dados, incluindo 'file_upload_id', 'movimentacoes_detalhada', 'novos_registros', etc.
        payload_safe = _convert_decimals_to_json_safe(payload)
        
        # 2. Inicializa o Serializer com os dados completos
        serializer = ProcessamentoFinalSerializer(data=payload_safe)

        if serializer.is_valid():
            try:
                # 3. Salva os dados, passando o usuário logado (request.user).
                # O Serializer (ProcessamentoFinalSerializer) é responsável por:
                # a) Deserializar 'movimentacoes_detalhada' e 'file_upload_id'.
                # b) Usar o payload completo (validado) para salvar no JSONField 'dados_requisicao'
                #    do modelo ProcessedFile.
                result = serializer.save(processed_by=request.user)
                
                # O Serializer agora é responsável por atualizar o process_status e criar o ProcessedFile,
                # mas mantemos a lógica de fallback de atualização de status do FileUpload aqui para garantir.
                upload_instance.process_status = result.get("status", "COMPLETED")
                upload_instance.save()
                
                return Response(
                    {
                        "detail": "Dados gravados com sucesso.",
                        "registros_processados": result.get("count"),
                        "status": "COMPLETED"
                    },
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                 # Em caso de erro na gravação principal (dentro do .save do Serializer)
                 upload_instance.process_status = "FAILED"
                 upload_instance.save()
                 # Logue o erro 'e' para depuração
                 return Response({"detail": f"Erro ao gravar: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Em caso de validação do Serializer falhar
        upload_instance.process_status = "FAILED"
        upload_instance.save()
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)