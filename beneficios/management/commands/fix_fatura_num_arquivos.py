import re
import io
from django.core.management.base import BaseCommand
from django.conf import settings
import boto3
from beneficios.models import FaturamentoArquivo


class Command(BaseCommand):
    help = 'Corrige fatura_num em FaturamentoArquivo: baixa PDFs do S3 e faz match de CNPJ para Notas de Debito'

    def handle(self, *args, **options):
        arquivos = FaturamentoArquivo.objects.filter(fatura_num='')
        total = arquivos.count()
        self.stdout.write(f'Processando {total} arquivos sem fatura_num...')

        s3 = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )
        bucket = getattr(settings, 'BUCKET_S3', 'fedcorp-prod')

        # Agrupar por faturamento_id
        por_faturamento = {}
        for arq in arquivos:
            fid = arq.faturamento_id
            if fid not in por_faturamento:
                por_faturamento[fid] = []
            por_faturamento[fid].append(arq)

        atualizados = 0
        erros = 0

        for fid, arquivos_sem_fatura in por_faturamento.items():
            self.stdout.write(f'\n--- Faturamento {fid} ---')

            # Primeiro: processar todos os boletos do faturamento para montar mapa de CNPJs
            # Pegar TODOS os arquivos do faturamento (incluindo os ja com fatura_num)
            todos_do_fat = FaturamentoArquivo.objects.filter(faturamento_id=fid)
            mapa_fatura_cnpjs = {}  # fatura_num -> set(cnpj_digits)

            for arq in todos_do_fat:
                if arq.tipo != 'boleto':
                    continue

                # Extrair fatura_num
                fatura_num = self._extrair_do_nome(arq.nome_arquivo)
                if not fatura_num:
                    fatura_num = arq.fatura_num  # ja pode estar preenchido

                if not fatura_num:
                    # Tentar extrair do S3
                    fatura_num = self._extrair_fatura_s3(s3, bucket, arq)

                if not fatura_num:
                    continue

                # Extrair CNPJs do conteudo
                cnpjs = self._extrair_cnpjs_s3(s3, bucket, arq)

                if fatura_num not in mapa_fatura_cnpjs:
                    mapa_fatura_cnpjs[fatura_num] = set()
                mapa_fatura_cnpjs[fatura_num].update(cnpjs)

                self.stdout.write(f'  Boleto: {arq.nome_arquivo} -> fatura={fatura_num}, cnjpjs={len(cnpjs)}')

            self.stdout.write(f'  Mapa construido: {mapa_fatura_cnpjs}')

            # Segundo: processar notas de debito e notas fiscais
            for arq in arquivos_sem_fatura:
                if arq.tipo == 'boleto':
                    fatura_num = self._extrair_do_nome(arq.nome_arquivo)
                    if not fatura_num:
                        fatura_num = self._extrair_fatura_s3(s3, bucket, arq)
                    if fatura_num:
                        arq.fatura_num = fatura_num
                        arq.save(update_fields=['fatura_num'])
                        atualizados += 1
                        self.stdout.write(f'  OK (boleto): {arq.nome_arquivo} -> fatura_num={fatura_num}')
                    else:
                        erros += 1
                        self.stdout.write(
                            self.style.WARNING(f'  ERRO (boleto): {arq.nome_arquivo}')
                        )
                else:
                    cnpjs = self._extrair_cnpjs_s3(s3, bucket, arq)
                    if not cnpjs:
                        erros += 1
                        self.stdout.write(
                            self.style.WARNING(f'  ERRO (cnpj): {arq.nome_arquivo} -> CNPJ nao encontrado')
                        )
                        continue

                    cnpj_principal = cnpjs[0]
                    cnpj_digits = re.sub(r'\D', '', cnpj_principal)

                    fatura_num = None
                    for fn, cnpjs_set in mapa_fatura_cnpjs.items():
                        for c in cnpjs_set:
                            if re.sub(r'\D', '', c) == cnpj_digits:
                                fatura_num = fn
                                break
                        if fatura_num:
                            break

                    if fatura_num:
                        arq.fatura_num = fatura_num
                        arq.save(update_fields=['fatura_num'])
                        atualizados += 1
                        self.stdout.write(f'  OK (match): {arq.nome_arquivo} -> fatura_num={fatura_num} (CNPJ {cnpj_principal})')
                    else:
                        erros += 1
                        self.stdout.write(
                            self.style.WARNING(f'  ERRO (match): {arq.nome_arquivo} -> CNPJ {cnpj_principal} nao encontrado em nenhum boleto do faturamento {fid}')
                        )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n\nConcluido: {atualizados} atualizados, {erros} erros'
            )
        )

    def _extrair_do_nome(self, nome):
        """Extrai numero de fatura (6+ digitos) do nome do arquivo."""
        match = re.search(r'(\d{6,})', nome)
        return match.group(1) if match else None

    def _extrair_fatura_s3(self, s3, bucket, arquivo):
        """Baixa PDF do S3 e extrai numero da fatura do conteudo."""
        try:
            conteudo = io.BytesIO()
            s3.download_fileobj(bucket, arquivo.s3_key, conteudo)
            conteudo.seek(0)

            from upload.pdf_reader import ler_boleto
            resultado = ler_boleto(conteudo)

            for pagina in resultado.get('paginas', []):
                fatura = pagina.get('fatura')
                if fatura:
                    return fatura
            return None
        except Exception:
            return None

    def _extrair_cnpjs_s3(self, s3, bucket, arquivo):
        """Baixa PDF do S3 e extrai CNPJs do conteudo."""
        try:
            conteudo = io.BytesIO()
            s3.download_fileobj(bucket, arquivo.s3_key, conteudo)
            texto = self._extrair_texto_pdf(conteudo)

            # Formato: XX.XXX.XXX/0001-XX
            cnpjs = re.findall(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', texto)
            if cnpjs:
                return cnpjs

            # 14 digitos juntos
            cnpjs_14 = re.findall(r'\b(\d{14})\b', texto)
            formatted = []
            for c in cnpjs_14:
                formatted.append(f'{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:14]}')
            return formatted
        except Exception:
            return []

    def _extrair_texto_pdf(self, file_obj):
        """Extrai texto de um PDF de um BytesIO."""
        from pypdf import PdfReader
        file_obj.seek(0)
        reader = PdfReader(file_obj)
        textos = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                textos.append(text)
        return '\n'.join(textos)
