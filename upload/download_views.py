import io
import zipfile
from rest_framework import views, status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
import boto3
from beneficios.models import Faturamento


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


class DownloadFaturamentoView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, faturamento_id):
        try:
            faturamento = Faturamento.objects.get(id=faturamento_id)
        except Faturamento.DoesNotExist:
            return HttpResponse("Faturamento não encontrado.", status=404)

        admin_nome = faturamento.administradora.nome if faturamento.administradora else "Sem Administradora"
        s3_prefix = f"{faturamento_id} - {admin_nome}"

        s3 = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )
        bucket = getattr(settings, 'BUCKET_S3', 'fedcorp-prod')

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for tipo in ['boleto', 'nota_debito', 'nota_fiscal']:
                prefix = f"VR - DOCS/faturamentos/{s3_prefix}/{tipo}/"
                tipo_display = {'boleto': 'Boleto', 'nota_debito': 'Nota de débito', 'nota_fiscal': 'Nota Fiscal'}.get(tipo, tipo)
                baixar_pdfs_s3(s3, bucket, prefix, zf, tipo_display)

        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="faturamento_{faturamento_id}_todos.zip"'
        return response


class DownloadArquivosView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    tipo = None

    def get(self, request, faturamento_id):
        try:
            faturamento = Faturamento.objects.get(id=faturamento_id)
        except Faturamento.DoesNotExist:
            return HttpResponse("Faturamento não encontrado.", status=404)

        admin_nome = faturamento.administradora.nome if faturamento.administradora else "Sem Administradora"
        s3_prefix = f"{faturamento_id} - {admin_nome}"

        s3 = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )
        bucket = getattr(settings, 'BUCKET_S3', 'fedcorp-prod')
        prefix = f"VR - DOCS/faturamentos/{s3_prefix}/{self.tipo}/"

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            baixar_pdfs_s3(s3, bucket, prefix, zf)

        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="faturamento_{faturamento_id}_{self.tipo}.zip"'
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
        try:
            faturamento = Faturamento.objects.get(id=faturamento_id)
        except Faturamento.DoesNotExist:
            return HttpResponse("Faturamento não encontrado.", status=404)

        admin_nome = faturamento.administradora.nome if faturamento.administradora else "Sem Administradora"
        s3_prefix = f"{faturamento_id} - {admin_nome}"
        tipo_display = {'boleto': 'Boleto', 'nota_debito': 'Nota de débito', 'nota_fiscal': 'Nota Fiscal'}.get(self.tipo, self.tipo)
        nome_arquivo = f"MERGED - {admin_nome} - {faturamento_id} - {tipo_display}.pdf"
        s3_key = f"VR - DOCS/faturamentos/{s3_prefix}/{self.tipo}/{nome_arquivo}"

        s3 = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )
        bucket = getattr(settings, 'BUCKET_S3', 'fedcorp-prod')

        try:
            s3.head_object(Bucket=bucket, Key=s3_key)
            url = f"https://{bucket}.s3.amazonaws.com/{s3_key}"
            return HttpResponseRedirect(url)
        except:
            return HttpResponse("Arquivo não encontrado.", status=404)


class DownloadBoletoOriginalView(DownloadArquivoOriginalView):
    tipo = 'boleto'


class DownloadNotaDebitoOriginalView(DownloadArquivoOriginalView):
    tipo = 'nota_debito'


class DownloadNotaFiscalOriginalView(DownloadArquivoOriginalView):
    tipo = 'nota_fiscal'
