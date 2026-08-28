import io
import zipfile
import logging
import requests
from rest_framework import views
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
from django.http import HttpResponse
import boto3
from beneficios.models import Faturamento, Boleto, Importacao
from pypdf import PdfReader, PdfWriter

from urllib.parse import quote

logger = logging.getLogger(__name__)


def _resolve_faturamentos(identificador):
    """
    Resolve um ID que pode ser Faturamento ou Importacao.
    Retorna lista de objetos Faturamento.
    Se nao encontrar nenhum, retorna lista vazia (a view chamadora trata erro).
    """
    try:
        return [Faturamento.objects.get(id=identificador)]
    except Faturamento.DoesNotExist:
        pass

    try:
        importacao = Importacao.objects.get(id=identificador)
        return list(importacao.faturamentos.all())
    except Importacao.DoesNotExist:
        return []


def _merge_notas_emitidas(faturamento):
    boletos = Boleto.objects.filter(
        faturamento=faturamento
    ).exclude(url_nota__isnull=True).exclude(url_nota='').order_by('documento')

    if not boletos.exists():
        return None

    writer = PdfWriter()
    notas_count = 0

    for boleto in boletos:
        try:
            response = requests.get(boleto.url_nota, timeout=20)
            if response.status_code == 200:
                pdf_file = io.BytesIO(response.content)
                reader = PdfReader(pdf_file)
                for page in reader.pages:
                    writer.add_page(page)
                notas_count += 1
        except Exception as e:
            logger.error(f"Erro ao baixar/mesclar nota do boleto {boleto.documento}: {e}")

    if notas_count == 0:
        return None

    buffer = io.BytesIO()
    writer.write(buffer)
    buffer.seek(0)
    return buffer


def baixar_pdfs_s3(s3, bucket, prefix, zf, subpasta=None):
    """Baixa PDFs do S3 e adiciona ao ZIP."""
    try:
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                key = obj['Key']
                if key.endswith('/') or not key.lower().endswith('.pdf'):
                    continue
                nome_arquivo = key.split('/')[-1]
                try:
                    f = io.BytesIO()
                    s3.download_fileobj(bucket, key, f)
                    f.seek(0)
                    if subpasta:
                        nome = f"{subpasta}/{nome_arquivo}"
                    else:
                        nome = nome_arquivo
                    zf.writestr(nome, f.read())
                except:
                    pass
    except:
        pass


def _baixar_originais_faturamento(s3, bucket, faturamento, tipo):
    """Retorna um PDF com todos os arquivos originais enviados para o tipo."""
    admin_nome = faturamento.administradora.razao_social if faturamento.administradora else "Sem Administradora"
    s3_prefix = f"VR - DOCS/faturamentos/{faturamento.id} - {admin_nome}/{tipo}/"
    originais_prefix = f"{s3_prefix}originais/"

    arquivos = []
    try:
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket, Prefix=originais_prefix):
            arquivos.extend(
                objeto['Key']
                for objeto in page.get('Contents', [])
                if objeto['Key'].lower().endswith('.pdf')
            )
    except Exception as exc:
        logger.warning(f"Erro ao listar originais do faturamento {faturamento.id}: {exc}")

    writer = PdfWriter()
    paginas = 0
    for chave in sorted(arquivos):
        try:
            conteudo = io.BytesIO()
            s3.download_fileobj(bucket, chave, conteudo)
            conteudo.seek(0)
            for pagina in PdfReader(conteudo).pages:
                writer.add_page(pagina)
                paginas += 1
        except Exception as exc:
            logger.warning(f"Erro ao ler original {chave}: {exc}")

    if paginas:
        resultado = io.BytesIO()
        writer.write(resultado)
        resultado.seek(0)
        return resultado

    # Compatibilidade com faturamentos gravados antes do armazenamento por arquivo.
    tipo_display = {
        'boleto': 'Boleto',
        'nota_debito': 'Nota de débito',
        'nota_fiscal': 'Nota Fiscal',
    }.get(tipo, tipo)
    chave_legada = f"{s3_prefix}MERGED - {admin_nome} - {faturamento.id} - {tipo_display}.pdf"
    try:
        resultado = io.BytesIO()
        s3.download_fileobj(bucket, chave_legada, resultado)
        resultado.seek(0)
        return resultado
    except Exception:
        return None


class DownloadFaturamentoView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, faturamento_id):
        faturas = _resolve_faturamentos(faturamento_id)
        if not faturas:
            return HttpResponse("Faturamento ou importação não encontrada.", status=404)

        s3 = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )
        bucket = getattr(settings, 'BUCKET_S3', 'fedcorp-prod')

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fat in faturas:
                admin_nome = fat.administradora.razao_social if fat.administradora else "Sem Administradora"
                s3_prefix = f"{fat.id} - {admin_nome}"
                for tipo in ['boleto', 'nota_debito', 'nota_fiscal', 'fatura']:
                    prefix = f"VR - DOCS/faturamentos/{s3_prefix}/{tipo}/"
                    tipo_display = {'boleto': 'Boleto', 'nota_debito': 'Nota de débito', 'nota_fiscal': 'Nota Fiscal', 'fatura': 'Fatura'}.get(tipo, tipo)
                    baixar_pdfs_s3(s3, bucket, prefix, zf, f"fatura_{fat.id}/{tipo_display}")

        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="faturamento_{faturamento_id}_todos.zip"'
        return response


class DownloadArquivosView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    tipo = None

    def get(self, request, faturamento_id):
        faturas = _resolve_faturamentos(faturamento_id)
        if not faturas:
            return HttpResponse("Faturamento ou importação não encontrada.", status=404)

        s3 = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )
        bucket = getattr(settings, 'BUCKET_S3', 'fedcorp-prod')

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fat in faturas:
                admin_nome = fat.administradora.razao_social if fat.administradora else "Sem Administradora"
                prefix = f"VR - DOCS/faturamentos/{fat.id} - {admin_nome}/{self.tipo}/"
                subpasta = f"fatura_{fat.id}"
                baixar_pdfs_s3(s3, bucket, prefix, zf, subpasta)

        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/zip')
        label = {'boleto': 'Boleto', 'nota_debito': 'NotaDebito', 'nota_fiscal': 'NotaFiscal'}.get(self.tipo, self.tipo)
        response['Content-Disposition'] = f'attachment; filename="{label}_{faturamento_id}.zip"'
        return response


class DownloadBoletosView(DownloadArquivosView):
    tipo = 'boleto'


class DownloadNotasDebitoView(DownloadArquivosView):
    tipo = 'nota_debito'


class DownloadNotasFiscaisView(DownloadArquivosView):
    tipo = 'nota_fiscal'


class DownloadArquivoOriginalView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    tipo = None

    def get(self, request, faturamento_id):
        faturas = _resolve_faturamentos(faturamento_id)
        if not faturas:
            return HttpResponse("Faturamento ou importação não encontrada.", status=404)

        tipo_display = {'boleto': 'Boleto', 'nota_debito': 'Nota de débito', 'nota_fiscal': 'Nota Fiscal'}.get(self.tipo, self.tipo)

        s3 = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )
        bucket = getattr(settings, 'BUCKET_S3', 'fedcorp-prod')

        writer = PdfWriter()
        total_paginas = 0
        for fat in faturas:
            buffer = _baixar_originais_faturamento(s3, bucket, fat, self.tipo)
            if buffer is not None:
                reader = PdfReader(buffer)
                for page in reader.pages:
                    writer.add_page(page)
                    total_paginas += 1

        if total_paginas == 0:
            return HttpResponse("Arquivo não encontrado.", status=404)

        admin_nome = faturas[0].administradora.razao_social if faturas[0].administradora else "Sem Administradora"
        sufixo = f"_{faturamento_id}" if len(faturas) == 1 else f"_importacao_{faturamento_id}"
        nome_arquivo = f"MERGED - {admin_nome} - {tipo_display}{sufixo}.pdf"

        resultado = io.BytesIO()
        writer.write(resultado)
        resultado.seek(0)
        response = HttpResponse(resultado.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
        return response


class DownloadTodosOriginaisView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, faturamento_id):
        faturas = _resolve_faturamentos(faturamento_id)
        if not faturas:
            return HttpResponse("Faturamento ou importação não encontrada.", status=404)

        s3 = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )
        bucket = getattr(settings, 'BUCKET_S3', 'fedcorp-prod')

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fat in faturas:
                admin_nome = fat.administradora.razao_social if fat.administradora else "Sem Administradora"
                for tipo, tipo_display in [
                    ('boleto', 'Boleto'),
                    ('nota_debito', 'Nota de débito'),
                    ('nota_fiscal', 'Nota Fiscal'),
                ]:
                    original = _baixar_originais_faturamento(s3, bucket, fat, tipo)
                    if original is not None:
                        zf.writestr(f"fatura_{fat.id}/{tipo_display}.pdf", original.read())

                if 'Nota Fiscal.pdf' not in zf.namelist():
                    notas_buffer = _merge_notas_emitidas(fat)
                    if notas_buffer is not None:
                        zf.writestr(f"fatura_{fat.id}/Nota Fiscal.pdf", notas_buffer.read())

        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="faturamento_{faturamento_id}_originais.zip"'
        return response


class DownloadBoletoOriginalView(DownloadArquivoOriginalView):
    tipo = 'boleto'


class DownloadNotaDebitoOriginalView(DownloadArquivoOriginalView):
    tipo = 'nota_debito'


class DownloadNotaFiscalOriginalView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, faturamento_id):
        try:
            faturamento = Faturamento.objects.get(id=faturamento_id)
        except Faturamento.DoesNotExist:
            return HttpResponse("Faturamento não encontrado.", status=404)

        s3 = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )
        bucket = getattr(settings, 'BUCKET_S3', 'fedcorp-prod')
        buffer = _baixar_originais_faturamento(s3, bucket, faturamento, 'nota_fiscal')
        if buffer is None:
            buffer = _merge_notas_emitidas(faturamento)
        if buffer is None:
            return HttpResponse("Nenhuma nota fiscal emitida disponível para este faturamento.", status=404)

        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="notas_fiscais_faturamento_{faturamento_id}.pdf"'
        return response
    

class DownloadArquivoView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, importacao_id):
        """
        Faz o download do arquivo original do S3
        """
        from beneficios.models import Importacao
        
        try:
            importacao = Importacao.objects.get(id=importacao_id)
            file_upload = importacao.file_upload
        except Importacao.DoesNotExist:
            return HttpResponse("Importação não encontrada", status=404)
        
        if not file_upload or not file_upload.s3_key:
            return HttpResponse("Arquivo não encontrado no S3", status=404)
        
        s3 = boto3.client(
            's3',
            aws_access_key_id=settings.ACCESS_KEY_S3,
            aws_secret_access_key=settings.SECRET_KEY_S3,
            region_name='us-east-2'
        )
        
        try:
            buffer = io.BytesIO()
            s3.download_fileobj(settings.BUCKET_S3, file_upload.s3_key, buffer)
            buffer.seek(0)
            response = HttpResponse(buffer.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{quote(file_upload.original_filename)}"'
            return response
        except:
            return HttpResponse("Arquivo não encontrado no S3.", status=404)


class DownloadNotasEmitidasView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, faturamento_id):
        faturas = _resolve_faturamentos(faturamento_id)
        if not faturas:
            return HttpResponse("Faturamento ou importação não encontrada.", status=404)

        writer = PdfWriter()
        total_notas = 0
        for fat in faturas:
            buffer = _merge_notas_emitidas(fat)
            if buffer is not None:
                reader = PdfReader(buffer)
                for page in reader.pages:
                    writer.add_page(page)
                    total_notas += 1

        if total_notas == 0:
            return HttpResponse("Nenhuma nota fiscal emitida disponível para este faturamento.", status=404)

        resultado = io.BytesIO()
        writer.write(resultado)
        resultado.seek(0)
        response = HttpResponse(resultado.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="notas_fiscais_faturamento_{faturamento_id}.pdf"'
        return response
