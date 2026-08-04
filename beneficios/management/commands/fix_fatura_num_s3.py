import base64
import io
import re
from django.core.management.base import BaseCommand
from django.conf import settings
import boto3
from beneficios.models import FaturamentoArquivo


class Command(BaseCommand):
    help = 'Corrige fatura_num em FaturamentoArquivo extraindo o número da fatura do conteúdo PDF no S3'

    def handle(self, *args, **options):
        arquivos_sem_fatura = FaturamentoArquivo.objects.filter(fatura_num='')
        total = arquivos_sem_fatura.count()
        self.stdout.write(f'Processando {total} arquivos sem fatura_num via S3...')

        s3 = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )
        bucket = getattr(settings, 'BUCKET_S3', 'fedcorp-prod')

        atualizados = 0
        erros = 0

        for arquivo in arquivos_sem_fatura:
            fatura_num = self._extrair_fatura_s3(s3, bucket, arquivo.s3_key)
            if fatura_num:
                arquivo.fatura_num = fatura_num
                arquivo.save(update_fields=['fatura_num'])
                atualizados += 1
                self.stdout.write(f'  OK: {arquivo.nome_arquivo} -> fatura_num={fatura_num}')
            else:
                erros += 1
                self.stdout.write(
                    self.style.WARNING(f'  ERRO: {arquivo.nome_arquivo} -> não foi possível extrair fatura do S3')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nConcluído: {atualizados} atualizados, {erros} erros'
            )
        )

    def _extrair_fatura_s3(self, s3, bucket, s3_key):
        """Baixa PDF do S3 e extrai o número da fatura do conteúdo."""
        try:
            conteudo = io.BytesIO()
            s3.download_fileobj(bucket, s3_key, conteudo)
            conteudo.seek(0)

            from upload.pdf_reader import ler_boleto
            resultado = ler_boleto(conteudo)

            for pagina in resultado.get('paginas', []):
                fatura = pagina.get('fatura')
                if fatura:
                    return fatura

            return None
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'    Exceção ao processar {s3_key}: {e}')
            )
            return None
