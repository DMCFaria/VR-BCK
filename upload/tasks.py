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

# Status a partir dos quais uma importação pode avançar para FATURADO.
#
# PENDING está FORA desta lista de propósito. O valor é sobrecarregado: além de
# ser o default do model, é uma opção que o operador escolhe no dropdown do
# dashboard para marcar "pagamento pendente" — um estado POSTERIOR ao
# faturamento. Avançar a partir dele apagaria uma decisão manual.
#
# Os demais status (COMPRADO, PAGO, PAGO_PARCIALMENTE, CANCELADO,
# BOLETO_VR_ENVIADO) também são posteriores ou terminais: enviar documentos
# adicionais não pode rebaixar o pedido.
STATUS_ANTERIORES_A_FATURADO = (
    'PROCESSING',
    'AGUARDANDO_FATURAMENTO',
    'FAILED',
)


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

            # Só marca is_searched quando o endereço realmente veio da consulta;
            # um endereço pré-existente (possivelmente errado, vindo da planilha)
            # não é sobrescrito aqui, e marcá-lo como pesquisado escondia o erro
            # das rotinas de correção/reconsulta.
            if any(c in campos_atualizados for c in ("endereco", "bairro", "cidade", "cep")):
                condominio.is_searched = True
                condominio.save(update_fields=campos_atualizados + ["is_searched"])
            elif campos_atualizados:
                condominio.save(update_fields=campos_atualizados)
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
        # Um envio pode conter boletos de MAIS DE UMA fatura (ex.: 176385 e
        # 176386 no mesmo pedido). Extrai a fatura de CADA arquivo: todas são
        # validadas/sincronizadas no FedHub e cada arquivo original é
        # carimbado com a própria fatura; a primeira segue como principal.
        fatura_por_arquivo = []
        for resultado in resultados_boleto:
            fat_arq = None
            for pagina in resultado['paginas']:
                if pagina.get('fatura'):
                    fat_arq = pagina.get('fatura')
                    break
            fatura_por_arquivo.append(fat_arq)
        faturas_unicas = list(dict.fromkeys(f for f in fatura_por_arquivo if f))
        fatura_num = faturas_unicas[0] if faturas_unicas else None

        from core.fedhub.services.fedhub_service import FedhubService
        from beneficios.models import Boleto
        from entidades.models import Condominio

        if arquivos_boleto:
            if not fatura_num:
                raise ValueError("Não foi possível extrair o número da fatura do boleto. Verifique o arquivo PDF.")

            fedhub_service = FedhubService()
            boletos_por_fatura = {}
            faturas_sem_boleto = []
            for fat_n in faturas_unicas:
                dados_fat = fedhub_service.buscar_todos_boletos_por_fatura(fat_n)
                if dados_fat:
                    boletos_por_fatura[fat_n] = dados_fat
                else:
                    faturas_sem_boleto.append(fat_n)

            if faturas_sem_boleto:
                raise ValueError(
                    f"Nenhum boleto encontrado no sistema para a(s) fatura(s) "
                    f"{', '.join(faturas_sem_boleto)}. Processamento bloqueado."
                )

            if mode != 'adicionar':
                _limpar_prefixo_s3(s3_client, bucket_name, s3_base_key)

            # Gravação centralizada em upload/boletos_sync.py (mesma lógica do
            # comando `sincronizar_boletos`). Se nenhum boleto for gravado — ex.:
            # FedHub devolveu itens sem 'documento' — o faturamento NÃO pode
            # concluir como se tivesse boletos: a consulta ficaria vazia em
            # silêncio (caso do faturamento 447 / fatura 175826).
            from upload.boletos_sync import gravar_boletos_fedhub
            total_gravados = total_itens = 0
            for fat_n, dados_fat in boletos_por_fatura.items():
                stats_boletos = gravar_boletos_fedhub(faturamento, fat_n, dados_fat)
                total_gravados += stats_boletos['gravados']
                total_itens += stats_boletos['total']
            if total_gravados == 0:
                raise ValueError(
                    f"FedHub devolveu {total_itens} boleto(s) para a(s) fatura(s) "
                    f"{', '.join(faturas_unicas)}, mas nenhum tinha número de documento — nada foi gravado. "
                    f"Verifique no FedHub e reprocesse (ou rode 'manage.py sincronizar_boletos')."
                )
            logger.info(
                f"Boletos para a(s) fatura(s) {', '.join(faturas_unicas)} validados e criados "
                f"com sucesso antes do upload ({total_gravados}/{total_itens})."
            )
        elif mode == 'adicionar':
            # Inclusão só de notas (débito/fiscal), sem boleto novo: não há
            # fatura para validar no FedHub nem boletos para regravar — a
            # exigência de boleto derrubava o faturamento inteiro (caso do
            # pedido 302, 28/08/2026). Recupera a fatura de um envio anterior
            # apenas para nomear os arquivos originais.
            fatura_num = (
                FaturamentoArquivo.objects
                .filter(faturamento=faturamento, tipo='boleto')
                .exclude(fatura_num='')
                .order_by('-criado_em')
                .values_list('fatura_num', flat=True)
                .first()
            ) or ''
            logger.info(
                f"[FATURAMENTO] Modo adicionar sem boleto novo: pulando validação FedHub "
                f"(fatura anterior: '{fatura_num or 'desconhecida'}')."
            )
        else:
            # Substituição sem boleto não deveria passar pela view; falha clara.
            raise ValueError("Substituição de documentos exige o arquivo de boleto.")

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

        _consolidar_documentos_multiplos(
            s3_client, bucket_name, s3_base_key, condominios_encontrados
        )

        _upload_arquivos_originais(
            s3_client,
            bucket_name,
            s3_base_key,
            arquivos_data,
            faturamento.id,
            FaturamentoArquivo,
            # Com mais de uma fatura no envio, notas/documentos sem fatura
            # própria ficam sem número (não dá para saber a qual pertencem).
            fatura_num if len(faturas_unicas) <= 1 else '',
            faturas_boleto=fatura_por_arquivo,
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

            # O avanço para FATURADO é responsabilidade do backend, não do
            # frontend: antes dependia de um PATCH que o front disparava após o
            # upload, e quando esse PATCH falhava a importação ficava presa no
            # status anterior mesmo com o faturamento concluído.
            #
            # O filtro por status torna a escrita condicional e idempotente:
            # avança quem ainda não foi faturado e não toca em quem já está
            # COMPRADO/PAGO/CANCELADO — inclusive no mode='adicionar', em que
            # documentos extras são anexados a um pedido já adiante no fluxo.
            avancou = Importacao.objects.filter(
                id=importacao_id,
                status__in=STATUS_ANTERIORES_A_FATURADO,
            ).update(status='FATURADO')

            if avancou:
                MovimentacaoBeneficio.objects.filter(
                    importacao=importacao_id
                ).update(importacao_status='FATURADO')
                logger.info(
                    f"[FATURAMENTO] Importacao {importacao_id} avançou para FATURADO"
                )
            else:
                logger.info(
                    f"[FATURAMENTO] Importacao {importacao_id} mantida no status atual "
                    f"(já posterior ao faturamento, ou cancelada)"
                )

            faturamento.status = 'COMPLETED'
            faturamento.save(update_fields=['status'])
            MovimentacaoBeneficio.objects.filter(importacao=importacao_id).update(fat_status='COMPLETED')
        except Exception:
            logger.exception("Erro ao atualizar status da importação para FATURADO")

        try:
            _disparar_email_boleto_cliente.delay(importacao_id)
            logger.info(f"[BOLETO_EMAIL] Task de envio de boleto agendada para importacao_id={importacao_id}")
        except Exception as exc:
            logger.warning(
                f"[BOLETO_EMAIL] Falha ao agendar task de envio de boleto "
                f"(importacao_id={importacao_id}): {exc}"
            )

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


def _consolidar_documentos_multiplos(s3_client, bucket_name, s3_base_key, condominios):
    """
    Um condomínio pode receber mais de uma página do mesmo tipo de documento
    (ex.: "nota de débito 1" e "nota de débito 2" no mesmo envio, ou uma nota
    de duas páginas). Antes, a última página sobrescrevia a URL das demais no
    FaturamentoDocumento. Aqui, quando há múltiplas, as páginas são mescladas
    num único PDF por condomínio+tipo e a URL consolidada substitui a última.
    As chaves internas '_<tipo>_urls' são removidas ao final.
    """
    from entidades.models import Condominio

    s3_base_key = f"VR - DOCS/faturamentos/{s3_base_key}" if '/' not in str(s3_base_key) else s3_base_key
    tipos_display = {'boleto': 'Boleto', 'nota_debito': 'Nota de débito', 'nota_fiscal': 'Nota Fiscal'}

    for cnpj, docs in condominios.items():
        for tipo, tipo_display in tipos_display.items():
            urls = docs.pop(f'_{tipo}_urls', [])
            if len(urls) <= 1:
                continue

            try:
                writer = PdfWriter()
                for url in urls:
                    key = url.split('.amazonaws.com/', 1)[1]
                    buf = io.BytesIO()
                    s3_client.download_fileobj(bucket_name, key, buf)
                    buf.seek(0)
                    for page in PdfReader(buf).pages:
                        writer.add_page(page)

                merged = io.BytesIO()
                writer.write(merged)
                merged.seek(0)

                try:
                    condo_nome = Condominio.objects.get(cnpj=cnpj).nome
                except Condominio.DoesNotExist:
                    condo_nome = cnpj

                nome_arquivo = f"CONSOLIDADO - {condo_nome} - {cnpj} - {tipo_display}.pdf"
                s3_key = f"{s3_base_key}/{tipo}/{nome_arquivo}"
                s3_client.upload_fileobj(
                    merged, bucket_name, s3_key,
                    ExtraArgs={'ContentType': 'application/pdf'}
                )
                docs[tipo] = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
                logger.info(
                    f"[CONSOLIDAR] {tipo_display} do condomínio {cnpj}: {len(urls)} páginas "
                    f"mescladas em '{nome_arquivo}'"
                )
            except Exception as e:
                # Mantém a última URL (comportamento anterior) em vez de falhar o faturamento.
                logger.error(f"[CONSOLIDAR] Falha ao mesclar {tipo} do condomínio {cnpj}: {e}")


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
        # Rastro de TODAS as páginas deste condomínio/tipo (chave interna com
        # '_'): quando houver mais de uma — duas notas de débito para o mesmo
        # condomínio, por exemplo — _consolidar_documentos_multiplos mescla
        # tudo num único PDF, em vez de a última página sobrescrever as demais.
        condominios[cnpj_limpo].setdefault(f'_{tipo}_urls', []).append(url)
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
    faturas_boleto=None,
):
    """`faturas_boleto`: fatura extraída de cada PDF de boleto, na mesma ordem
    de arquivos_data['boleto'] — cada boleto é carimbado com a PRÓPRIA fatura
    (um envio pode conter boletos de faturas diferentes)."""
    for tipo, dados in arquivos_data.items():
        if not dados:
            continue

        if isinstance(dados, dict):
            dados = [dados]

        for indice, arquivo in enumerate(dados, start=1):
            fatura_arquivo = fatura_num
            if tipo == 'boleto' and faturas_boleto and len(faturas_boleto) >= indice and faturas_boleto[indice - 1]:
                fatura_arquivo = faturas_boleto[indice - 1]
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
                    'fatura_num': fatura_arquivo,
                    'nome_arquivo': nome_original,
                    'url': f"https://{bucket_name}.s3.amazonaws.com/{s3_key}",
                },
            )

            logger.debug(f"Upload arquivo original {tipo}: {nome_arquivo}")


# Limite do S3 para URLs pre-assinadas geradas com credenciais de longo prazo
# (SigV4): 7 dias. Nao ha como emitir link direto com validade maior que isso.
LINK_BOLETO_EXPIRACAO_MAX_SEGUNDOS = 7 * 24 * 3600


def _nome_arquivo_seguro(nome, fallback):
    """Remove caracteres que quebrariam o header Content-Disposition."""
    limpo = (nome or '').strip().replace('"', '').replace('\r', '').replace('\n', '')
    return limpo or fallback


def _gerar_link_download_boleto(s3_client, bucket_name, arquivo, expiracao_segundos):
    """
    Gera URL pre-assinada para download direto do boleto.

    O bucket e privado (nenhum upload usa ACL public-read), portanto a URL
    publica gravada em FaturamentoArquivo.url retorna AccessDenied. O link
    enviado por e-mail precisa ser assinado.

    Confere a existencia do objeto antes de assinar: generate_presigned_url
    nao valida a chave, e um link para chave inexistente falharia somente na
    mao do cliente.

    Retorna None se o objeto nao existir ou a assinatura falhar.
    """
    s3_key = arquivo.s3_key
    nome_arquivo = _nome_arquivo_seguro(arquivo.nome_arquivo, f'boleto_{arquivo.id}.pdf')

    try:
        s3_client.head_object(Bucket=bucket_name, Key=s3_key)
    except Exception as exc:
        logger.warning(
            f"[BOLETO_EMAIL] Objeto ausente no S3, link nao gerado: {s3_key} ({exc})"
        )
        return None

    params = {
        'Bucket': bucket_name,
        'Key': s3_key,
        'ResponseContentType': 'application/pdf',
        'ResponseContentDisposition': f'attachment; filename="{nome_arquivo}"',
    }

    try:
        # Header HTTP nao transporta non-ASCII de forma confiavel; nesse caso
        # deixa o S3 nomear o download a partir da propria chave.
        nome_arquivo.encode('ascii')
    except UnicodeEncodeError:
        params.pop('ResponseContentDisposition')

    try:
        return s3_client.generate_presigned_url(
            'get_object',
            Params=params,
            ExpiresIn=expiracao_segundos,
        )
    except Exception as exc:
        logger.warning(f"[BOLETO_EMAIL] Falha ao assinar link de {s3_key}: {exc}")
        return None


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def _disparar_email_boleto_cliente(self, importacao_id):
    """
    Apos processar_faturamento, envia e-mail com links de download dos boletos.

    Os boletos NAO seguem como anexo: o gateway de e-mail do FedHub
    (POST /api/email/send/gmail) nao suporta anexos -- o modelo EmailRequest
    nao declara o campo e o Pydantic descarta extras em silencio, entao o
    e-mail chegava sempre sem os PDFs. O e-mail leva links pre-assinados do S3.
    """
    from beneficios.models import FaturamentoArquivo, Importacao
    from core.fedhub.services.fedhub_service import FedhubService

    bucket_name = getattr(settings, 'BUCKET_S3', 'fedcorp-prod')
    expiracao = min(
        int(getattr(
            settings,
            'BOLETO_LINK_EXPIRACAO_SEGUNDOS',
            LINK_BOLETO_EXPIRACAO_MAX_SEGUNDOS,
        )),
        LINK_BOLETO_EXPIRACAO_MAX_SEGUNDOS,
    )

    try:
        importacao = Importacao.objects.get(id=importacao_id)

        if not importacao.usuario or not importacao.usuario.email:
            logger.warning(f"[BOLETO_EMAIL] Importacao {importacao_id} não tem usuario ou email. Pulando envio.")
            return {"status": "skipped", "reason": "no_email"}

        email_destino = importacao.usuario.email

        # Uma importacao pode ter varios faturamentos (envios adicionais de
        # documentos criam novos). Antes esta task fazia
        # Faturamento.objects.get(id=importacao_id), usando o ID da importacao
        # como ID de faturamento -- chaves de tabelas distintas, o que ora
        # falhava em silencio, ora anexava boletos de outro cliente.
        faturamentos = list(importacao.faturamentos.all())
        if not faturamentos:
            logger.warning(f"[BOLETO_EMAIL] Importacao {importacao_id} sem faturamentos. Pulando envio.")
            return {"status": "skipped", "reason": "no_faturamentos"}

        boletos = list(
            FaturamentoArquivo.objects.filter(
                faturamento__in=faturamentos,
                tipo='boleto',
            ).order_by('faturamento_id', 'criado_em', 'id')
        )
        if not boletos:
            logger.warning(f"[BOLETO_EMAIL] Nenhum boleto encontrado para importacao_id={importacao_id}")
            return {"status": "skipped", "reason": "no_boletos"}

        logger.info(
            f"[BOLETO_EMAIL] Enviando {len(boletos)} boleto(s) de "
            f"{len(faturamentos)} faturamento(s) para: {email_destino} "
            f"(importacao_id={importacao_id})"
        )

        s3_client = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'ACCESS_KEY_S3', ''),
            aws_secret_access_key=getattr(settings, 'SECRET_KEY_S3', ''),
            region_name='us-east-2'
        )

        boletos_context = []
        for arquivo in boletos:
            link = _gerar_link_download_boleto(s3_client, bucket_name, arquivo, expiracao)
            if not link:
                continue
            boletos_context.append({
                'nome': _nome_arquivo_seguro(arquivo.nome_arquivo, f'boleto_{arquivo.id}.pdf'),
                'fatura': arquivo.fatura_num or '',
                'link': link,
            })

        if not boletos_context:
            logger.error(
                f"[BOLETO_EMAIL] Nenhum link pôde ser gerado para importacao_id={importacao_id} "
                f"({len(boletos)} boleto(s) registrado(s), todos ausentes no S3). E-mail não enviado."
            )
            return {"status": "skipped", "reason": "no_links"}

        if len(boletos_context) < len(boletos):
            logger.warning(
                f"[BOLETO_EMAIL] importacao_id={importacao_id}: "
                f"{len(boletos) - len(boletos_context)} de {len(boletos)} boleto(s) "
                f"sem link (ausentes no S3). E-mail seguirá parcial."
            )

        competencia_str = ''
        for fat in faturamentos:
            if fat.competencia:
                competencia_str = fat.competencia.strftime('%m/%Y')
                break

        context = {
            'cliente_nome': importacao.usuario.nome or importacao.usuario.email.split('@')[0],
            'competencia': competencia_str,
            'vencimento': importacao.data_vencimento.strftime('%d/%m/%Y') if importacao.data_vencimento else None,
            'valor_total': f"R$ {float(importacao.valor_total or 0):,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.'),
            'boletos': boletos_context,
            'link_validade_dias': max(1, expiracao // (24 * 3600)),
            'prazo_pagamento': 'O pagamento deverá ser realizado até a data de vencimento informada no boleto.'
        }

        fedhub_service = FedhubService()
        enviado = fedhub_service.enviar_email_boleto(
            email=email_destino,
            context=context,
        )

        if enviado:
            importacao.status = 'BOLETO_VR_ENVIADO'
            importacao.save(update_fields=['status'])
            logger.info(
                f"[BOLETO_EMAIL] E-mail enviado e status atualizado para "
                f"importacao_id={importacao_id} ({len(boletos_context)} link(s))"
            )
            return {
                "status": "sent",
                "to": email_destino,
                "links": len(boletos_context),
                "boletos_sem_link": len(boletos) - len(boletos_context),
            }
        else:
            logger.error(f"[BOLETO_EMAIL] Falha ao enviar e-mail para importacao_id={importacao_id}")
            return {"status": "failed"}

    except Importacao.DoesNotExist:
        logger.error(f"[BOLETO_EMAIL] Importacao {importacao_id} não encontrada")
        return {"status": "error", "reason": "importacao_not_found"}
    except Exception as e:
        logger.exception(f"[BOLETO_EMAIL] Erro ao enviar boleto: {e}")
        raise self.retry(exc=e)

