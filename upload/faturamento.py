import base64
import io
import logging
import unicodedata
from datetime import datetime
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db import transaction

from beneficios.models import Faturamento, Importacao
from upload.pdf_reader import ler_boleto, classificar_pdf_por_conteudo
from core.fedhub.services.fedhub_service import FedhubService
from .tasks import processar_faturamento

logger = logging.getLogger(__name__)


def _sem_acentos(texto):
    """Nome de arquivo com acento ('NOTA DÉBITO') precisa casar com 'debito'."""
    return unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')


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

        arquivos_boleto = []
        arquivos_nota_debito = []
        arquivos_nota_fiscal = []
        arquivos_fatura = []

        # MultiValueDict.items() retorna apenas o último arquivo de cada campo.
        # Use lists() para não descartar arquivos quando o usuário envia vários PDFs.
        mode = request.data.get('mode', 'substituir')

        nao_identificados = []
        for nome_campo, arquivos_campo in arquivos.lists():
            for arquivo in arquivos_campo:
                # 1ª passada: pelo nome (campo ou arquivo), sem acentos —
                # 'NOTA DÉBITO.pdf' precisa casar com 'debito'.
                nome_lower = _sem_acentos(nome_campo.lower())
                real_name_lower = _sem_acentos(getattr(arquivo, 'name', '').lower())
                if (
                    'reciboq' in nome_lower
                    or 'boleto' in nome_lower
                    or 'reciboq' in real_name_lower
                    or 'boleto' in real_name_lower
                ):
                    arquivos_boleto.append(arquivo)
                elif 'debito' in nome_lower or 'debito' in real_name_lower:
                    arquivos_nota_debito.append(arquivo)
                elif 'nf' in nome_lower or 'nf' in real_name_lower:
                    arquivos_nota_fiscal.append(arquivo)
                elif 'fatura' in nome_lower or 'fatura' in real_name_lower:
                    # Fatura emitida pela VR (FATURA-<numero>.PDF): NÃO é
                    # aceita no envio de documentos (decisão de 28/08/2026,
                    # EV-SES-007) — detectamos só para rejeitar com mensagem
                    # clara, em vez do genérico "tipo não identificado".
                    arquivos_fatura.append(getattr(arquivo, 'name', nome_campo))
                else:
                    # 2ª passada: pelo conteúdo do PDF — o nome do arquivo
                    # deixa de ser obrigatório.
                    tipo_conteudo = classificar_pdf_por_conteudo(arquivo)
                    if tipo_conteudo == 'boleto':
                        arquivos_boleto.append(arquivo)
                    elif tipo_conteudo == 'nota_debito':
                        arquivos_nota_debito.append(arquivo)
                    elif tipo_conteudo == 'nota_fiscal':
                        arquivos_nota_fiscal.append(arquivo)
                    else:
                        nao_identificados.append(getattr(arquivo, 'name', nome_campo))

        # No modo 'adicionar' o pedido já tem documentos: aceita qualquer
        # subconjunto (ex.: incluir só uma nota fiscal). Boleto + nota de
        # débito continuam obrigatórios no fluxo de substituição/importação.
        erros = []
        if arquivos_fatura:
            erros.append(
                f"Arquivos de FATURA não são aceitos no envio de documentos: {', '.join(arquivos_fatura)}. "
                "Remova-os da lista e envie apenas boleto, nota de débito e nota fiscal."
            )
        if nao_identificados:
            erros.append(
                "Não foi possível identificar o tipo (boleto, nota de débito ou nota fiscal) "
                f"pelo nome nem pelo conteúdo de: {', '.join(nao_identificados)}. "
                "Verifique se o PDF está legível ou renomeie o arquivo indicando o tipo."
            )
        if mode == 'adicionar':
            if not (arquivos_boleto or arquivos_nota_debito or arquivos_nota_fiscal):
                erros.append("Nenhum arquivo de boleto, nota de débito ou nota fiscal reconhecido.")
        else:
            if not arquivos_boleto:
                erros.append("Arquivo de BOLETO não encontrado entre os enviados.")
            if not arquivos_nota_debito:
                erros.append("Arquivo de NOTA DE DÉBITO não encontrado entre os enviados.")

        if erros:
            return Response(
                {"detail": "Erro na validação dos arquivos.", "erros": erros},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validação síncrona do boleto: extrai fatura e verifica se existe no
        # Fedhub. Só quando há boleto no envio (modo adicionar pode não ter).
        if arquivos_boleto:
            try:
                boleto_bytes = arquivos_boleto[0].read()
                arquivos_boleto[0].seek(0)
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

                if mode == 'adicionar':
                    if existing_faturamento:
                        faturamento = existing_faturamento
                        faturamento.status = 'PENDING'
                        faturamento.save(update_fields=['status'])
                    else:
                        faturamento = Faturamento.objects.create(
                            id=importacao_id,
                            importacao=importacao,
                            administradora=importacao.administradora,
                            competencia=competencia,
                            criado_por=request.user,
                            status='PENDING'
                        )
                else:
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
                'boleto': [
                    {
                        'nome': arquivo.name,
                        'content': base64.b64encode(arquivo.read()).decode('utf-8'),
                    }
                    for arquivo in arquivos_boleto
                ],
                'nota_debito': [
                    {
                        'nome': arquivo.name,
                        'content': base64.b64encode(arquivo.read()).decode('utf-8'),
                    }
                    for arquivo in arquivos_nota_debito
                ],
            }

            if arquivos_nota_fiscal:
                arquivos_data['nota_fiscal'] = [
                    {
                        'nome': arquivo.name,
                        'content': base64.b64encode(arquivo.read()).decode('utf-8'),
                    }
                    for arquivo in arquivos_nota_fiscal
                ]

            processar_faturamento.delay(
                importacao_id=importacao_id,
                competencia=competencia.isoformat(),
                arquivos_data=arquivos_data,
                usuario_id=request.user.id,
                mode=mode
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


class ExcluirArquivoFaturamentoView(views.APIView):
    """
    Exclui um documento importado do faturamento (registro + arquivo no S3).
    DELETE /api/upload/faturamento/arquivo/<arquivo_id>/

    Restrito a dev/fat. Observação: as páginas por condomínio já derivadas
    desse arquivo NÃO são recalculadas — para refazer o retrato por
    condomínio, reenvie os documentos corretos (modo substituir).
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def delete(self, request, arquivo_id):
        if getattr(request.user, 'tipo', None) not in ('dev', 'fat'):
            return Response(
                {'detail': 'Sem permissão para excluir documentos do faturamento.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        from django.conf import settings
        from beneficios.models import FaturamentoArquivo

        try:
            arquivo = FaturamentoArquivo.objects.get(id=arquivo_id)
        except FaturamentoArquivo.DoesNotExist:
            return Response({'detail': 'Documento não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        info = {
            'id': arquivo.id,
            'nome': arquivo.nome_arquivo,
            'tipo': arquivo.tipo,
            'faturamento': arquivo.faturamento_id,
            's3_key': arquivo.s3_key,
        }

        # Remove do S3 (best-effort: a exclusão do registro não pode ficar
        # presa a uma falha transitória do S3; a chave fica no log).
        try:
            import boto3
            s3 = boto3.client(
                's3',
                aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
                aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
                region_name='us-east-2',
            )
            s3.delete_object(Bucket=getattr(settings, 'BUCKET_S3', 'fedcorp-prod'), Key=arquivo.s3_key)
        except Exception as e:
            logger.warning(f"[EXCLUIR_ARQUIVO] Falha ao remover do S3 ({info['s3_key']}): {e}")

        arquivo.delete()
        logger.info(f"[EXCLUIR_ARQUIVO] user={request.user.id} ({request.user.tipo}) excluiu {info}")

        return Response({'detail': f"Documento '{info['nome']}' excluído."})


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
                "erro_mensagem": faturamento.erro_mensagem,
                "competencia": faturamento.competencia,
                "criado_em": faturamento.criado_em
            })
        except Faturamento.DoesNotExist:
            return Response(
                {"detail": "Faturamento não encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )
