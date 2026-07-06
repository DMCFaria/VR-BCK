import base64
import io
import logging
from datetime import datetime
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db import transaction

from beneficios.models import Faturamento, Importacao
from upload.pdf_reader import ler_boleto
from core.fedhub.services.fedhub_service import FedhubService
from .tasks import processar_faturamento

logger = logging.getLogger(__name__)


class UploadFaturamentoView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):
        arquivos = request.FILES

        if not arquivos:
            return Response(
                {"detail": "Nenhum arquivo enviado."},
                status=status.HTTP_400_BAD_REQUEST
            )

        importacao_id = request.data.get('importacao_id')
        competencia = request.data.get('competencia')

        if not importacao_id:
            return Response(
                {"detail": "O campo 'importacao_id' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not competencia:
            return Response(
                {"detail": "O campo 'competencia' é obrigatório (formato: YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            competencia = datetime.strptime(competencia, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {"detail": "Formato de competência inválido. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            importacao = Importacao.objects.get(id=importacao_id)
        except Importacao.DoesNotExist:
            return Response(
                {"detail": "Importação não encontrada."},
                status=status.HTTP_404_NOT_FOUND
            )

        arquivo_boleto = None
        arquivo_nota_debito = None
        arquivo_nota_fiscal = None

        for nome_arquivo, arquivo in arquivos.items():
            nome_lower = nome_arquivo.lower()
            real_name_lower = getattr(arquivo, 'name', '').lower()
            if 'reciboq' in nome_lower or 'boleto' in nome_lower or 'reciboq' in real_name_lower or 'boleto' in real_name_lower:
                arquivo_boleto = arquivo
            elif 'debito' in nome_lower or 'dédito' in nome_lower or 'debito' in real_name_lower or 'dédito' in real_name_lower:
                arquivo_nota_debito = arquivo
            elif 'nf' in nome_lower or 'nf' in real_name_lower:
                arquivo_nota_fiscal = arquivo

        erros = []
        if not arquivo_boleto:
            erros.append("Arquivo de BOLETO não encontrado. O nome deve conter 'RECIBOQ' ou 'BOLETO'.")
        if not arquivo_nota_debito:
            erros.append("Arquivo de NOTA DE DÉBITO não encontrado. O nome deve conter 'DEBITO'.")

        if erros:
            return Response(
                {"detail": "Erro na validação dos arquivos.", "erros": erros},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validação síncrona do boleto: extrai fatura e verifica se existe no Fedhub
        try:
            boleto_bytes = arquivo_boleto.read()
            arquivo_boleto.seek(0)
            boleto_io = io.BytesIO(boleto_bytes)
            resultado_boleto = ler_boleto(boleto_io)

            fatura_previa = None
            for pagina in resultado_boleto.get('paginas', []):
                if pagina.get('fatura'):
                    fatura_previa = pagina.get('fatura')
                    break

            if not fatura_previa:
                return Response(
                    {"detail": "Não foi possível identificar o número da fatura no boleto. Verifique o arquivo enviado."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            fedhub = FedhubService()
            boletos_previa = fedhub.buscar_todos_boletos_por_fatura(fatura_previa)

            if not boletos_previa:
                return Response(
                    {"detail": f"Nenhum boleto encontrado no sistema para a fatura {fatura_previa}. A emissão foi bloqueada."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.warning(f"Falha na validação prévia do boleto: {e}")

        try:
            with transaction.atomic():
                existing_faturamento = Faturamento.objects.filter(importacao_id=importacao_id).first()
                if existing_faturamento:
                    existing_faturamento.documentos.all().delete()
                    existing_faturamento.delete()

                faturamento = Faturamento.objects.create(
                    id=importacao_id,
                    importacao=importacao,
                    administradora=importacao.administradora,
                    competencia=competencia,
                    criado_por=request.user,
                    status='PENDING'
                )

            arquivos_data = {
                'boleto': {
                    'nome': arquivo_boleto.name,
                    'content': base64.b64encode(arquivo_boleto.read()).decode('utf-8')
                },
                'nota_debito': {
                    'nome': arquivo_nota_debito.name,
                    'content': base64.b64encode(arquivo_nota_debito.read()).decode('utf-8')
                }
            }

            if arquivo_nota_fiscal:
                arquivos_data['nota_fiscal'] = {
                    'nome': arquivo_nota_fiscal.name,
                    'content': base64.b64encode(arquivo_nota_fiscal.read()).decode('utf-8')
                }

            processar_faturamento.delay(
                importacao_id=importacao_id,
                competencia=competencia.isoformat(),
                arquivos_data=arquivos_data,
                usuario_id=request.user.id
            )

            return Response({
                "detail": "Processamento iniciado em background.",
                "faturamento_id": faturamento.id,
                "importacao_id": importacao_id,
                "status": "PENDING"
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response(
                {"detail": f"Erro ao iniciar processamento: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StatusFaturamentoView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, faturamento_id):
        try:
            faturamento = Faturamento.objects.get(id=faturamento_id)
            return Response({
                "faturamento_id": faturamento.id,
                "status": faturamento.status,
                "progresso": faturamento.progresso,
                "competencia": faturamento.competencia,
                "criado_em": faturamento.criado_em
            })
        except Faturamento.DoesNotExist:
            return Response(
                {"detail": "Faturamento não encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )