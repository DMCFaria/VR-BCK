import decimal
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
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
    Necessário porque o PostgreSQL JSONField e o Django Response não suportam Decimal nativamente.
    """
    if isinstance(data, decimal.Decimal):
        return str(data)
    if isinstance(data, dict):
        return {k: _convert_decimals_to_json_safe(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_convert_decimals_to_json_safe(item) for item in data]
    return data

def _get_beneficiary_summary(parsed_data):
    """
    Calcula o total de benefícios por funcionário a partir da lista detalhada (planilha).
    CORREÇÃO: Agora lê a chave 'movimentacoes_detalhada' gerada pelo novo parser.
    """
    # Pega a lista plana gerada pelo parser (a 'planilha')
    movimentacoes_detalhada = parsed_data.get('movimentacoes_detalhada', [])

    # Dicionários para agregação
    total_por_cpf = defaultdict(decimal.Decimal)
    nomes_por_cpf = {}

    for row in movimentacoes_detalhada:
        # As chaves agora são as definidas na sua 'movimentacoes_detalhada'
        cpf = row.get('cpf_func')
        nome = row.get('nome_func')
        
        # O parser já calculou o total da linha neste campo
        valor = row.get('valor_recarga_bene')

        if cpf and valor is not None:
            # Garante que é Decimal para somar
            if not isinstance(valor, decimal.Decimal):
                try:
                    valor = decimal.Decimal(str(valor))
                except:
                    valor = decimal.Decimal(0)
            
            total_por_cpf[cpf] += valor
            # Guarda o nome para usar no resumo final
            nomes_por_cpf[cpf] = nome

    # Monta a lista final de resumo
    summary_list = []
    for cpf, total in total_por_cpf.items():
        summary_list.append({
            "nome_funcionario": nomes_por_cpf.get(cpf, "Nome não encontrado"),
            "cpf": cpf,
            "valor_total": total # Será convertido para string depois
        })
    
    return summary_list


# --- VIEWS ---

class UploadView(views.APIView):
    """
    Endpoint para fazer o upload do arquivo.
    Realiza o parsing, gera o resumo por funcionário e prepara os dados para o frontend.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # 1. Validação inicial do arquivo
        serializer = FileUploadSerializer(data=request.data)
        if serializer.is_valid():
            
            # 2. SALVAR O ARQUIVO (Injetando usuário para evitar IntegrityError)
            upload_instance = serializer.save(
                uploaded_by=request.user, 
                process_status="PENDING"
            )
            
            # 3. CHAMAR O PARSER
            file_path = upload_instance.file.path
            parsed_data = parse_rb_layout(file_path, upload_instance.id)

            # Verifica erros do parser
            if "error" in parsed_data:
                upload_instance.process_status = "FAILED"
                error_msg = {"error": parsed_data["error"]}
                upload_instance.summary_data = _convert_decimals_to_json_safe(error_msg)
                upload_instance.save()
                return Response(
                    {"detail": f"Falha no parsing: {parsed_data['error']}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 4. PREPARAR O RESUMO (SUMMARY) PARA O FRONTEND
            # Pega os dados brutos do parser
            raw_summary = parsed_data.get("summary", {})
            
            # Gera o resumo específico por beneficiário (CORRIGIDO)
            beneficiary_summary = _get_beneficiary_summary(parsed_data)

            # Monta o objeto de resumo final
            frontend_summary = {
                "total_condominios": raw_summary.get("total_condominios", 0),
                "total_funcionarios": raw_summary.get("total_funcionarios", 0),
                "total_movimentacoes": raw_summary.get("total_movimentacoes", 0),
                "valor_total_beneficios": raw_summary.get("valor_total_beneficios", 0),
                "data_competencia_arquivo": raw_summary.get("data_competencia_arquivo"),
                "total_por_beneficiario": beneficiary_summary # Agora virá preenchido
            }
            
            # 5. PREPARAR OS DADOS PARA O BACKEND (Payload completo)
            # O frontend enviará este objeto de volta na confirmação
            data_to_backend = {
                **parsed_data, 
                "file_upload_id": upload_instance.id
            }

            # 6. ATUALIZAR E SALVAR (Convertendo Decimais para JSON Safe)
            upload_instance.process_status = "PARSED"
            # Salva o resumo no banco para histórico
            upload_instance.summary_data = _convert_decimals_to_json_safe(frontend_summary)
            upload_instance.save()

            # 7. RESPOSTA DA API
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


class ConfirmationView(views.APIView):
    """
    Endpoint para confirmar a persistência.
    Recebe o objeto 'data_to_backend' (possivelmente modificado pelo frontend).
    """
    permission_classes = [IsAuthenticated] 

    def post(self, request, *args, **kwargs):
        # O frontend deve enviar o conteúdo de 'data_to_backend' no corpo da requisição
        payload = request.data
        file_id = payload.get("file_upload_id")

        if not file_id:
            return Response(
                {"detail": "O campo 'file_upload_id' é obrigatório no payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1. Verifica o status atual
        upload_instance = get_object_or_404(FileUpload, id=file_id)
        if upload_instance.process_status != "PARSED":
            return Response(
                {"detail": "Arquivo não está no status correto (PARSED) para confirmação."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. PREPARAÇÃO DOS DADOS
        # Apenas garantimos que Decimais venham como strings (caso o frontend tenha mexido em algo)
        payload_safe = _convert_decimals_to_json_safe(payload)

        # 3. SALVAMENTO ATÔMICO
        serializer = ProcessamentoFinalSerializer(data=payload_safe)

        if serializer.is_valid():
            try:
                # O método .create() do Serializer contém a transaction.atomic()
                result = serializer.save()
                
                # Atualiza status final
                upload_instance.process_status = result.get("status", "COMPLETED")
                upload_instance.save()
                
                return Response(
                    {
                        "detail": "Dados persistidos com sucesso.",
                        "movimentacoes_salvas": result.get("count", 0),
                        "status_final": "COMPLETED"
                    },
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                 # Captura erro de banco (IntegrityError, etc)
                 # Atualiza para FAILED em caso de erro no banco
                 upload_instance.process_status = "FAILED"
                 upload_instance.save()
                 return Response(
                    {"detail": f"Erro ao salvar no banco de dados: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # 4. Falha na validação
        upload_instance.process_status = "FAILED"
        upload_instance.save()
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)