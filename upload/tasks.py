import io
import re
import base64
import logging
from celery import shared_task
import boto3
from django.conf import settings
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def processar_faturamento(self, importacao_id, competencia, arquivos_data, usuario_id):
    from beneficios.models import Faturamento, FaturamentoDocumento, Importacao
    from entidades.models import Condominio
    from upload.pdf_reader import ler_boleto, ler_nota_debito, ler_nota_fiscal
    from django.contrib.auth import get_user_model

    from datetime import datetime

    User = get_user_model()
    bucket_name = getattr(settings, 'BUCKET_S3', 'fedcorp-prod')
    
    if isinstance(competencia, str):
        competencia = datetime.strptime(competencia, '%Y-%m-%d').date()

    def atualizar_progresso(faturamento_id, percentual, status=None):
        from beneficios.models import Faturamento
        update_fields = {'progresso': percentual}
        if status:
            update_fields['status'] = status
        Faturamento.objects.filter(id=faturamento_id).update(**update_fields)

    s3_client = None
    faturamento = None
    
    try:
        importacao = Importacao.objects.get(id=importacao_id)
        usuario = User.objects.get(id=usuario_id)

        s3_client = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )

        arquivo_boleto = io.BytesIO(base64.b64decode(arquivos_data['boleto']['content']))
        arquivo_nota_debito = io.BytesIO(base64.b64decode(arquivos_data['nota_debito']['content']))
        arquivo_nota_fiscal = None
        if arquivos_data.get('nota_fiscal'):
            arquivo_nota_fiscal = io.BytesIO(base64.b64decode(arquivos_data['nota_fiscal']['content']))

        logger.info(f"Processando faturamento para importação ID: {importacao_id}")

        resultado_boleto = ler_boleto(arquivo_boleto)
        resultado_nota_debito = ler_nota_debito(arquivo_nota_debito)
        
        resultado_nota_fiscal = None
        if arquivo_nota_fiscal:
            resultado_nota_fiscal = ler_nota_fiscal(arquivo_nota_fiscal)
        
        faturamento = Faturamento.objects.get(id=importacao_id)
        faturamento.status = 'PROCESSING'
        faturamento.save(update_fields=['status'])

        total_paginas = (
            len(resultado_boleto['paginas']) + 
            len(resultado_nota_debito['paginas']) + 
            (len(resultado_nota_fiscal['paginas']) if resultado_nota_fiscal else 0)
        )
        
        paginas_processadas = [0]
        
        if total_paginas > 0:
            paginas_por_10_percento = total_paginas / 9
        else:
            paginas_por_10_percento = 1

        def verificar_progresso():
            percentual = min(int(paginas_processadas[0] / paginas_por_10_percento) * 10, 90)
            atualizar_progresso(faturamento.id, percentual)

        condominios_encontrados = {}

        admin_nome = faturamento.administradora.nome if faturamento.administradora else "Sem Administradora"
        s3_base_key = f"VR - DOCS/faturamentos/{faturamento.id} - {admin_nome}"

        _processar_e_upload_paginas(
            s3_client, bucket_name, s3_base_key, arquivo_boleto, 
            resultado_boleto, 'boleto', condominios_encontrados, paginas_processadas, verificar_progresso
        )

        _processar_e_upload_paginas(
            s3_client, bucket_name, s3_base_key, arquivo_nota_debito, 
            resultado_nota_debito, 'nota_debito', condominios_encontrados, paginas_processadas, verificar_progresso
        )

        if arquivo_nota_fiscal:
            _processar_e_upload_paginas(
                s3_client, bucket_name, s3_base_key, arquivo_nota_fiscal, 
                resultado_nota_fiscal, 'nota_fiscal', condominios_encontrados, paginas_processadas, verificar_progresso
            )

        _upload_arquivos_originais(s3_client, bucket_name, s3_base_key, arquivos_data, admin_nome, faturamento.id)

        atualizar_progresso(faturamento.id, 90)

        logger.info(f"CNPJs encontrados: {list(condominios_encontrados.keys())}")

        total_condominios = len(condominios_encontrados)
        for i, (cnpj, docs) in enumerate(condominios_encontrados.items()):
            try:
                condominio = Condominio.objects.get(cnpj=cnpj)
            except Condominio.DoesNotExist:
                logger.warning(f"Condomínio {cnpj} não encontrado no banco, pulando...")
                continue

            FaturamentoDocumento.objects.create(
                faturamento=faturamento,
                condominio=condominio,
                url_boleto=docs.get('boleto', ''),
                url_nota_debito=docs.get('nota_debito', ''),
                url_nota_fiscal=docs.get('nota_fiscal', '')
            )
            
            progresso_banco = 90 + int(((i + 1) / total_condominios) * 10) if total_condominios > 0 else 100
            atualizar_progresso(faturamento.id, progresso_banco)

        atualizar_progresso(faturamento.id, 100, 'COMPLETED')

        try:
            from beneficios.models import Importacao
            Importacao.objects.filter(id=importacao_id).update(status='COMPLETED')
        except Exception:
            logger.exception("Erro ao atualizar status da importação para COMPLETED")

        logger.info(f"Faturamento {faturamento.id} concluído com {total_condominios} condomínios")

        return {
            "faturamento_id": faturamento.id,
            "total_condominios": total_condominios,
            "status": "COMPLETED"
        }

    except Exception as e:
        logger.exception(f"Erro ao processar faturamento: {str(e)}")
        
        try:
            Faturamento.objects.filter(id=importacao_id).update(status='FAILED', progresso=0)
        except Exception:
            logger.exception("Erro ao atualizar status para FAILED")
        
        raise self.retry(exc=e)


def _processar_e_upload_paginas(s3_client, bucket_name, s3_base_key, pdf_file, resultado, tipo, condominios, paginas_processadas, on_progress=None):
    from entidades.models import Condominio

    s3_base_key = f"VR - DOCS/faturamentos/{s3_base_key}" if '/' not in str(s3_base_key) else s3_base_key

    tipo_display = {'boleto': 'Boleto', 'nota_debito': 'Nota de débito', 'nota_fiscal': 'Nota Fiscal'}.get(tipo, tipo)

    pdf_file.seek(0)
    reader = PdfReader(pdf_file)

    for pagina_info in resultado['paginas']:
        numero_pagina = pagina_info['numero_pagina']
        cnpj = pagina_info.get('cnpj') or f"sem_cnpj_{numero_pagina}"
        cnpj_limpo = re.sub(r'[^0-9]', '', cnpj)

        condominio = None
        try:
            condominio = Condominio.objects.get(cnpj=cnpj_limpo)
        except Condominio.DoesNotExist:
            pass

        condo_nome = condominio.nome if condominio else cnpj_limpo
        seq = str(numero_pagina).zfill(3)
        nome_arquivo = f"{seq} - {condo_nome} - {cnpj_limpo} - {tipo_display}.pdf"

        page = reader.pages[numero_pagina - 1]
        writer = PdfWriter()
        writer.add_page(page)

        pdf_bytes = io.BytesIO()
        writer.write(pdf_bytes)
        pdf_bytes.seek(0)

        s3_key = f"{s3_base_key}/{tipo}/{nome_arquivo}"

        logger.debug(f"Upload {tipo} página {numero_pagina}: {nome_arquivo}")

        s3_client.upload_fileobj(
            pdf_bytes,
            bucket_name,
            s3_key,
            ExtraArgs={'ContentType': 'application/pdf'}
        )

        url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"

        if cnpj_limpo not in condominios:
            condominios[cnpj_limpo] = {}
        condominios[cnpj_limpo][tipo] = url

        paginas_processadas[0] += 1
        if on_progress:
            on_progress()


def _upload_arquivos_originais(s3_client, bucket_name, s3_base_key, arquivos_data, admin_nome, faturamento_id):
    import io
    from pypdf import PdfReader, PdfWriter

    for tipo, dados in arquivos_data.items():
        if not dados:
            continue

        tipo_display = {'boleto': 'Boleto', 'nota_debito': 'Nota de débito', 'nota_fiscal': 'Nota Fiscal'}.get(tipo, tipo)
        nome_arquivo = f"MERGED - {admin_nome} - {faturamento_id} - {tipo_display}.pdf"

        pdf_bytes = io.BytesIO(base64.b64decode(dados['content']))
        s3_key = f"{s3_base_key}/{tipo}/{nome_arquivo}"

        s3_client.upload_fileobj(
            pdf_bytes,
            bucket_name,
            s3_key,
            ExtraArgs={'ContentType': 'application/pdf'}
        )

        logger.debug(f"Upload arquivo original {tipo}: {nome_arquivo}")