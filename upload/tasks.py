import io
import re
import base64
import logging
import hashlib
from celery import shared_task
import boto3
from django.db import models
from django.conf import settings
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


def _notificar_erro_pesquisa_cnpj(assunto, mensagem):
    """Envia email de alerta quando a pesquisa automática de CNPJ falha."""
    from django.core.mail import send_mail
    from django.conf import settings

    email_destino = getattr(settings, 'EMAIL_FATURAMENTO', 'danielmello@condomed.com.br')
    try:
        send_mail(
            subject=assunto,
            message=mensagem,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@fedcorp.com.br'),
            recipient_list=[email_destino],
            fail_silently=False,
        )
        logger.info(f"[PESQUISA_CNPJ] Email de erro enviado para {email_destino}")
    except Exception as e:
        logger.exception(f"[PESQUISA_CNPJ] Falha ao enviar email de erro: {e}")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def pesquisar_enderecos_condominios(self, cnpjs, importacao_id=None):
    """
    Pesquisa os endereços dos condomínios em segundo plano usando BigDataCorp.

    Args:
        cnpjs: lista de CNPJs (com ou sem formatação) para pesquisar.
        importacao_id: ID da importação relacionada (apenas para log).
    """
    from entidades.models import Condominio
    from upload.services import CNPJConsultaService
    from django.conf import settings

    if not cnpjs:
        logger.info("[PESQUISA_CNPJ] Nenhum CNPJ para pesquisar.")
        return {"pesquisados": 0, "atualizados": 0, "importacao_id": importacao_id}

    # Verifica configuração das credenciais antes de começar
    if not getattr(settings, "BIGDATA_ACCESS_TOKEN", "") or not getattr(settings, "BIGDATA_TOKEN_ID", ""):
        erro_msg = (
            "[PESQUISA_CNPJ] BIGDATA_ACCESS_TOKEN ou BIGDATA_TOKEN_ID não configurados. "
            "A pesquisa automática de CNPJs não pode ser executada. "
            f"Importação: {importacao_id}"
        )
        logger.error(erro_msg)
        _notificar_erro_pesquisa_cnpj(
            "[ALERTA] Pesquisa automática de CNPJ - Credenciais não configuradas",
            erro_msg
        )
        return {"pesquisados": 0, "atualizados": 0, "importacao_id": importacao_id, "erro": "Credenciais não configuradas"}

    cnpjs_unicos = list(set(re.sub(r"\D", "", str(c)) for c in cnpjs if c))
    logger.info(
        f"[PESQUISA_CNPJ] Iniciando pesquisa de {len(cnpjs_unicos)} CNPJs "
        f"para importacao_id={importacao_id}"
    )

    pesquisados = 0
    atualizados = 0
    cnpjs_com_falha = []

    for cnpj in cnpjs_unicos:
        if len(cnpj) != 14:
            logger.warning(f"[PESQUISA_CNPJ] CNPJ ignorado (tamanho inválido): {cnpj}")
            continue

        try:
            condominio = Condominio.objects.filter(cnpj=cnpj).first()
            if not condominio:
                logger.warning(f"[PESQUISA_CNPJ] Condomínio {cnpj} não encontrado no banco.")
                continue

            if condominio.is_searched:
                logger.info(f"[PESQUISA_CNPJ] Condomínio {cnpj} já pesquisado anteriormente.")
                continue

            dados = CNPJConsultaService.consultar(cnpj)
            pesquisados += 1

            if not dados:
                logger.warning(f"[PESQUISA_CNPJ] Não foi possível obter dados para {cnpj}.")
                cnpjs_com_falha.append(cnpj)
                continue

            campos_atualizados = []

            # Nome: sempre atualiza quando a consulta retorna um nome mais completo,
            # evitando abreviações preenchidas pelas administradoras.
            if dados.get("razao_social"):
                novo_nome = dados["razao_social"]
                if condominio.nome != novo_nome:
                    condominio.nome = novo_nome
                    campos_atualizados.append("nome")

            # Endereço: preenche apenas campos vazios para manter a planilha como fonte fiel.
            if dados.get("rua") and not condominio.endereco:
                condominio.endereco = dados["rua"]
                campos_atualizados.append("endereco")

            if dados.get("numero") and not condominio.numero:
                condominio.numero = dados["numero"]
                campos_atualizados.append("numero")

            if dados.get("complemento") and not condominio.complemento:
                condominio.complemento = dados["complemento"]
                campos_atualizados.append("complemento")

            if dados.get("bairro") and not condominio.bairro:
                condominio.bairro = dados["bairro"]
                campos_atualizados.append("bairro")

            if dados.get("cidade") and not condominio.cidade:
                condominio.cidade = dados["cidade"]
                campos_atualizados.append("cidade")

            if dados.get("estado") and not condominio.estado:
                condominio.estado = dados["estado"]
                campos_atualizados.append("estado")

            if dados.get("cep") and not condominio.cep:
                condominio.cep = dados["cep"]
                campos_atualizados.append("cep")

            condominio.is_searched = True
            condominio.save(update_fields=campos_atualizados + ["is_searched"])
            atualizados += 1

            logger.info(
                f"[PESQUISA_CNPJ] Condomínio {cnpj} atualizado: {campos_atualizados}"
            )

        except Exception as e:
            logger.exception(f"[PESQUISA_CNPJ] Erro ao processar CNPJ {cnpj}: {e}")
            cnpjs_com_falha.append(cnpj)
            continue

    # Notifica por email se houve falhas
    if cnpjs_com_falha:
        erro_msg = (
            f"[PESQUISA_CNPJ] A pesquisa automática de CNPJ falhou para os seguintes CNPJs "
            f"da importação {importacao_id}:\n\n" + "\n".join(cnpjs_com_falha) +
            f"\n\nTotal: {len(cnpjs_com_falha)} de {pesquisados} pesquisados."
        )
        logger.warning(erro_msg)
        _notificar_erro_pesquisa_cnpj(
            f"[ALERTA] Pesquisa automática de CNPJ - {len(cnpjs_com_falha)} falhas",
            erro_msg
        )

    logger.info(
        f"[PESQUISA_CNPJ] Finalizado. Pesquisados: {pesquisados}, "
        f"atualizados: {atualizados}, importacao_id={importacao_id}"
    )

    return {
        "pesquisados": pesquisados,
        "atualizados": atualizados,
        "importacao_id": importacao_id,
        "falhas": cnpjs_com_falha,
    }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def processar_faturamento(self, importacao_id, competencia, arquivos_data, usuario_id, mode='substituir'):
    from beneficios.models import Faturamento, FaturamentoArquivo, FaturamentoDocumento, Importacao
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

        def normalizar_arquivos(arquivos):
            if not arquivos:
                return []
            if isinstance(arquivos, dict):
                arquivos = [arquivos]
            return [
                io.BytesIO(base64.b64decode(arquivo['content']))
                for arquivo in arquivos
            ]

        arquivos_boleto = normalizar_arquivos(arquivos_data.get('boleto'))
        arquivos_nota_debito = normalizar_arquivos(arquivos_data.get('nota_debito'))
        arquivos_nota_fiscal = normalizar_arquivos(arquivos_data.get('nota_fiscal'))

        logger.info(f"Processando faturamento para importação ID: {importacao_id}")

        resultados_boleto = []
        for arquivo in arquivos_boleto:
            arquivo.seek(0)
            resultados_boleto.append(ler_boleto(arquivo))

        resultados_nota_debito = []
        for arquivo in arquivos_nota_debito:
            arquivo.seek(0)
            resultados_nota_debito.append(ler_nota_debito(arquivo))

        resultados_nota_fiscal = []
        for arquivo in arquivos_nota_fiscal:
            arquivo.seek(0)
            resultados_nota_fiscal.append(ler_nota_fiscal(arquivo))
        
        faturamento = Faturamento.objects.get(id=importacao_id)
        faturamento.status = 'PROCESSING'
        faturamento.save(update_fields=['status'])

        total_paginas = sum(
            len(resultado['paginas'])
            for resultado in (
                resultados_boleto + resultados_nota_debito + resultados_nota_fiscal
            )
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

        admin_nome = faturamento.administradora.razao_social if faturamento.administradora else "Sem Administradora"
        s3_base_key = f"VR - DOCS/faturamentos/{faturamento.id} - {admin_nome}"

        # --- VALIDAÇÃO E CRIAÇÃO DE BOLETOS (antes de qualquer upload) ---
        fatura_num = None
        for resultado in resultados_boleto:
            for pagina in resultado['paginas']:
                if pagina.get('fatura'):
                    fatura_num = pagina.get('fatura')
                    break
            if fatura_num:
                break

        if not fatura_num:
            raise ValueError("Não foi possível extrair o número da fatura do boleto. Verifique o arquivo PDF.")

        from core.fedhub.services.fedhub_service import FedhubService
        from beneficios.models import Boleto
        from entidades.models import Condominio

        fedhub_service = FedhubService()
        boletos_data = fedhub_service.buscar_todos_boletos_por_fatura(fatura_num)

        if not boletos_data:
            raise ValueError(f"Nenhum boleto encontrado no sistema para a fatura {fatura_num}. Processamento bloqueado.")

        if mode != 'adicionar':
            _limpar_prefixo_s3(s3_client, bucket_name, s3_base_key)

        def parse_date_safe(date_str):
            if not date_str:
                return None
            try:
                return datetime.strptime(str(date_str), '%Y-%m-%d').date()
            except ValueError:
                try:
                    return datetime.strptime(str(date_str), '%d/%m/%Y').date()
                except ValueError:
                    return None

        for dados_boleto in boletos_data:
            cnpj_cobrado_raw = dados_boleto.get("cnpj_cobrado") or ""
            cnpj_cobrado_limpo = re.sub(r'[^0-9]', '', str(cnpj_cobrado_raw))
            condominio_exists = Condominio.objects.filter(cnpj=cnpj_cobrado_limpo).exists()

            doc_num = dados_boleto.get("documento")
            if doc_num:
                Boleto.objects.update_or_create(
                    documento=doc_num,
                    defaults={
                        "faturamento": faturamento,
                        "fatura": fatura_num,
                        "dt_emissao": parse_date_safe(dados_boleto.get("dt_emissao")),
                        "codigo_de_barra": dados_boleto.get("codigo_de_barra"),
                        "qr_code": dados_boleto.get("qr_code"),
                        "qr_imagem": dados_boleto.get("qr_imagem"),
                        "vencimento": parse_date_safe(dados_boleto.get("vencimento")),
                        "nome_cobrado": dados_boleto.get("nome_cobrado"),
                        "cnpj_cobrado": cnpj_cobrado_limpo or cnpj_cobrado_raw,
                        "cedente": dados_boleto.get("cedente"),
                        "cnpj_cedente": dados_boleto.get("cnpj_cedente"),
                        "valor": dados_boleto.get("valor"),
                        "deducoes": dados_boleto.get("deducoes"),
                        "status": dados_boleto.get("status"),
                        "nosso_numero": dados_boleto.get("nosso_numero"),
                        "identificador": dados_boleto.get("identificador"),
                        "baixa": bool(dados_boleto.get("baixa", False)),
                        "dt_baixa": parse_date_safe(dados_boleto.get("dt_baixa")),
                        "obs_baixa": dados_boleto.get("obs_baixa"),
                        "NFs_id": dados_boleto.get("nfs_id"),
                        "Numero_nota": dados_boleto.get("numero_nota"),
                        "url_nota": dados_boleto.get("url_nota") or None,
                        "match": condominio_exists,
                    }
                )
        logger.info(f"Boletos para a fatura {fatura_num} validados e criados com sucesso antes do upload.")

        # --- UPLOADS S3 (só executa se a validação dos boletos passou) ---
        for arquivo_indice, (arquivo, resultado) in enumerate(zip(arquivos_boleto, resultados_boleto), start=1):
            _processar_e_upload_paginas(
                s3_client, bucket_name, s3_base_key, arquivo,
                resultado, 'boleto', condominios_encontrados, paginas_processadas, verificar_progresso,
                arquivo_indice
            )

        for arquivo_indice, (arquivo, resultado) in enumerate(zip(arquivos_nota_debito, resultados_nota_debito), start=1):
            _processar_e_upload_paginas(
                s3_client, bucket_name, s3_base_key, arquivo,
                resultado, 'nota_debito', condominios_encontrados, paginas_processadas, verificar_progresso,
                arquivo_indice
            )

        for arquivo_indice, (arquivo, resultado) in enumerate(zip(arquivos_nota_fiscal, resultados_nota_fiscal), start=1):
            _processar_e_upload_paginas(
                s3_client, bucket_name, s3_base_key, arquivo,
                resultado, 'nota_fiscal', condominios_encontrados, paginas_processadas, verificar_progresso,
                arquivo_indice
            )

        _upload_arquivos_originais(
            s3_client,
            bucket_name,
            s3_base_key,
            arquivos_data,
            faturamento.id,
            FaturamentoArquivo,
            fatura_num,
        )

        atualizar_progresso(faturamento.id, 90)

        logger.info(f"CNPJs encontrados: {list(condominios_encontrados.keys())}")

        total_condominios = len(condominios_encontrados)
        for i, (cnpj, docs) in enumerate(condominios_encontrados.items()):
            try:
                condominio = Condominio.objects.get(cnpj=cnpj)
            except Condominio.DoesNotExist:
                logger.warning(f"Condomínio {cnpj} não encontrado no banco, pulando...")
                continue

            if mode == 'adicionar':
                documento_existente = FaturamentoDocumento.objects.filter(
                    faturamento=faturamento,
                    condominio=condominio,
                ).first()
                defaults = {
                    campo: valor
                    for campo, valor in {
                        'url_boleto': docs.get('boleto', ''),
                        'url_nota_debito': docs.get('nota_debito', ''),
                        'url_nota_fiscal': docs.get('nota_fiscal', ''),
                    }.items()
                    if valor
                }
                if documento_existente:
                    for campo, valor in defaults.items():
                        setattr(documento_existente, campo, valor)
                    if defaults:
                        documento_existente.save(update_fields=list(defaults))
                else:
                    FaturamentoDocumento.objects.create(
                        faturamento=faturamento,
                        condominio=condominio,
                        url_boleto=defaults.get('url_boleto', ''),
                        url_nota_debito=defaults.get('url_nota_debito', ''),
                        url_nota_fiscal=defaults.get('url_nota_fiscal', ''),
                    )
            else:
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
            from beneficios.models import Importacao, MovimentacaoBeneficio
            from upload.nfse_service import emitir_nfse_lote

            condominios_novos = []
            condominios_existentes = set()

            if mode == 'adicionar':
                condominios_existentes = set(
                    FaturamentoDocumento.objects.filter(
                        faturamento=faturamento
                    ).values_list('condominio__cnpj', flat=True)
                )

            dados_condominios = []
            for cnpj, docs in condominios_encontrados.items():
                try:
                    condominio = Condominio.objects.get(cnpj=cnpj)
                except Condominio.DoesNotExist:
                    logger.warning(f"NFSe: Condomínio {cnpj} não encontrado, pulando...")
                    continue

                if mode == 'adicionar' and cnpj in condominios_existentes:
                    logger.info(f"NFSe: Condomínio {cnpj} já possui NFSe, pulando reemissão")
                    continue

                # PRIORIDADE 1: Buscar valor do boleto (Fedhub)
                boleto_valor = Boleto.objects.filter(
                    faturamento=faturamento,
                    cnpj_cobrado=cnpj,
                ).values_list('valor', flat=True).first()

                if boleto_valor:
                    total_valor = boleto_valor
                    logger.info(f"NFSe: Valor do boleto para {cnpj}: R$ {total_valor}")
                else:
                    # FALLBACK: Somar de MovimentacaoBeneficio
                    total_valor = MovimentacaoBeneficio.objects.filter(
                        importacao=importacao,
                        empresa_cnpj=condominio,
                    ).aggregate(total=models.Sum('valor_beneficio'))['total'] or 0
                    logger.info(f"NFSe: Valor calculado (fallback) para {cnpj}: R$ {total_valor}")

                servico_discriminacao = (
                    f"Serviços de administração de benefícios - "
                    f"Competência {faturamento.competencia.strftime('%m/%Y')} - "
                    f"Faturamento #{faturamento.id}"
                )

                numero_fatura = docs.get('fatura', '') or str(faturamento.id)

                dados_condominios.append((condominio, float(total_valor), servico_discriminacao, numero_fatura))

            if dados_condominios:
                emitir_nfse_lote(faturamento, dados_condominios)
                logger.info(f"Lote NFSe enviado para {len(dados_condominios)} condomínios")
        except Exception:
            logger.exception("Erro ao emitir NFSe para condomínios")

        try:
            from beneficios.models import Importacao, MovimentacaoBeneficio
            if mode != 'adicionar':
                Importacao.objects.filter(id=importacao_id).update(status='FATURADO')
                MovimentacaoBeneficio.objects.filter(importacao=importacao_id).update(importacao_status='FATURADO')
            faturamento.status = 'COMPLETED'
            faturamento.save(update_fields=['status'])
            MovimentacaoBeneficio.objects.filter(importacao=importacao_id).update(fat_status='COMPLETED')
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


def _processar_e_upload_paginas(
    s3_client,
    bucket_name,
    s3_base_key,
    pdf_file,
    resultado,
    tipo,
    condominios,
    paginas_processadas,
    on_progress=None,
    arquivo_indice=1,
):
    from entidades.models import Condominio

    s3_base_key = f"VR - DOCS/faturamentos/{s3_base_key}" if '/' not in str(s3_base_key) else s3_base_key

    tipo_display = {'boleto': 'Boleto', 'nota_debito': 'Nota de débito', 'nota_fiscal': 'Nota Fiscal'}.get(tipo, tipo)

    pdf_file.seek(0)
    reader = PdfReader(pdf_file)

    for pagina_info in resultado['paginas']:
        numero_pagina = pagina_info['numero_pagina']
        cnpj = pagina_info.get('cnpj') or f"sem_cnpj_{numero_pagina}"
        cnpj_limpo = re.sub(r'[^0-9]', '', cnpj)
        fatura = pagina_info.get('fatura') or ''

        condominio = None
        try:
            condominio = Condominio.objects.get(cnpj=cnpj_limpo)
        except Condominio.DoesNotExist:
            pass

        condo_nome = condominio.nome if condominio else cnpj_limpo
        seq = str(numero_pagina).zfill(3)
        nome_arquivo = f"{seq}-{arquivo_indice:03d} - {condo_nome} - {cnpj_limpo} - {tipo_display}.pdf"

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
        if tipo == 'boleto' and fatura:
            condominios[cnpj_limpo]['fatura'] = fatura

        paginas_processadas[0] += 1
        if on_progress:
            on_progress()


def _limpar_prefixo_s3(s3_client, bucket_name, prefix):
    """Remove arquivos da geração anterior quando o upload substitui documentos."""
    objetos = []
    paginator = s3_client.get_paginator('list_objects_v2')
    for pagina in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        objetos.extend({'Key': item['Key']} for item in pagina.get('Contents', []))

    for inicio in range(0, len(objetos), 1000):
        lote = objetos[inicio:inicio + 1000]
        if lote:
            s3_client.delete_objects(Bucket=bucket_name, Delete={'Objects': lote})


def _upload_arquivos_originais(
    s3_client,
    bucket_name,
    s3_base_key,
    arquivos_data,
    faturamento_id,
    arquivo_model,
    fatura_num='',
):
    for tipo, dados in arquivos_data.items():
        if not dados:
            continue

        if isinstance(dados, dict):
            dados = [dados]

        for indice, arquivo in enumerate(dados, start=1):
            nome_original = str(arquivo.get('nome') or f'{tipo}.pdf').replace('/', '_').replace('\\', '_')
            conteudo = base64.b64decode(arquivo['content'])
            identificador = hashlib.sha256(conteudo).hexdigest()[:12]
            nome_arquivo = f"{indice:03d} - {identificador} - {nome_original}"
            pdf_bytes = io.BytesIO(conteudo)
            s3_key = f"{s3_base_key}/{tipo}/originais/{nome_arquivo}"

            s3_client.upload_fileobj(
                pdf_bytes,
                bucket_name,
                s3_key,
                ExtraArgs={'ContentType': 'application/pdf'}
            )

            arquivo_model.objects.update_or_create(
                s3_key=s3_key,
                defaults={
                    'faturamento_id': faturamento_id,
                    'tipo': tipo,
                    'fatura_num': fatura_num,
                    'nome_arquivo': nome_original,
                    'url': f"https://{bucket_name}.s3.amazonaws.com/{s3_key}",
                },
            )

            logger.debug(f"Upload arquivo original {tipo}: {nome_arquivo}")
