import io
import zipfile
from rest_framework import views
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
import boto3
from beneficios.models import Faturamento
from django.http import HttpResponse


def baixar_pdfs_s3(s3, bucket, prefix, zf, subpasta=None):
    """Baixa PDFs do S3 e adiciona ao ZIP."""
    try:
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                key = obj['Key']
                if key.endswith('/') or not key.lower().endswith('.pdf'):
                    continue
                cnpj = key.split('/')[-1].replace('.pdf', '').replace('.PDF', '')
                try:
                    f = io.BytesIO()
                    s3.download_fileobj(bucket, key, f)
                    f.seek(0)
                    nome = f"{cnpj}/{subpasta}.pdf" if subpasta else f"{cnpj}.pdf"
                    zf.writestr(nome, f.read())
                except:
                    pass
    except:
        pass


class DownloadFaturamentoView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, faturamento_id):
        if not Faturamento.objects.filter(id=faturamento_id).exists():
            return HttpResponse("Faturamento não encontrado.", status=404)

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
                prefix = f"VR - DOCS/faturamentos/{faturamento_id}/{tipo}/"
                baixar_pdfs_s3(s3, bucket, prefix, zf, tipo)

        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="faturamento_{faturamento_id}_todos.zip"'
        return response


class DownloadArquivosView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    tipo = None

    def get(self, request, faturamento_id):
        if not Faturamento.objects.filter(id=faturamento_id).exists():
            return HttpResponse("Faturamento não encontrado.", status=404)

        s3 = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )
        bucket = getattr(settings, 'BUCKET_S3', 'fedcorp-prod')
        prefix = f"VR - DOCS/faturamentos/{faturamento_id}/{self.tipo}/"

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
