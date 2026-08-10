import logging
import re
import time

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)

CAMPOS_ENDERECO = ('endereco', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'cep')


class Command(BaseCommand):
    """
    Corrige o endereço de condomínios que ficaram com o endereço da ADMINISTRADORA.

    Quando a administradora usa cartão admin, a planilha da VR traz o endereço
    dela como local de entrega, igual para todos os condomínios. Até a correção
    em upload/serializers.py, esse endereço era gravado no cadastro do condomínio
    na primeira importação — e como os campos ficavam preenchidos, a consulta por
    CNPJ do faturamento nunca disparava. O endereço errado seguia para a planilha
    de faturamento, o TXT de compra e a nota de débito.

    Critério de seleção (confirmado com o time antes de rodar):
      - condomínio vinculado a administradora com cartao_admin=True
      - is_searched=False, ou seja, o endereço gravado veio da planilha e não
        da consulta por CNPJ

    Roda em simulação por padrão. Use --apply para gravar.
    """

    help = "Corrige endereços de condomínios que receberam o endereço da administradora (cartão admin)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Grava as alterações. Sem esta flag o comando apenas simula.",
        )
        parser.add_argument(
            "--administradora",
            type=int,
            default=None,
            help="Restringe a uma administradora (id). Recomendado para o primeiro teste.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Processa no máximo N condomínios.",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.5,
            help="Espera entre consultas, em segundos. Padrão: 0.5",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        from entidades.models import Condominio
        from upload.services import CNPJConsultaService

        aplicar = options["apply"]
        administradora_id = options["administradora"]
        limit = options["limit"]
        sleep = options["sleep"]

        if not getattr(settings, "BIGDATA_ACCESS_TOKEN", "") or not getattr(settings, "BIGDATA_TOKEN_ID", ""):
            self.stderr.write(self.style.ERROR("BIGDATA_ACCESS_TOKEN ou BIGDATA_TOKEN_ID não configurados."))
            return

        qs = Condominio.objects.filter(
            vinculocondominio__administradora__cartao_admin=True,
            is_searched=False,
        ).distinct().order_by('cnpj')

        if administradora_id:
            qs = qs.filter(vinculocondominio__administradora_id=administradora_id)

        total = qs.count()

        if limit:
            qs = qs[:limit]

        modo = self.style.WARNING("APLICANDO (grava no banco)") if aplicar else self.style.SUCCESS("SIMULAÇÃO (nada será gravado)")
        self.stdout.write(f"Modo: {modo}")
        self.stdout.write(f"Condomínios no critério: {total}" + (f" | processando {limit}" if limit else ""))
        self.stdout.write("")

        consultados = 0
        alterados = 0
        sem_dados = 0
        falhas = 0

        for idx, condominio in enumerate(qs, start=1):
            cnpj = re.sub(r"\D", "", str(condominio.cnpj or ""))

            if len(cnpj) != 14:
                self.stdout.write(f"[{idx}] CNPJ inválido, pulando: {condominio.cnpj!r}")
                continue

            try:
                dados = CNPJConsultaService.consultar(cnpj, fonte="bigdatacorp_addresses")
                consultados += 1
            except Exception as e:
                logger.exception(f"Erro ao consultar CNPJ {cnpj}: {e}")
                self.stdout.write(self.style.ERROR(f"[{idx}] ERRO ao consultar {cnpj}: {e}"))
                falhas += 1
                continue

            if not dados:
                self.stdout.write(f"[{idx}] {cnpj} — consulta sem dados, mantido como está")
                sem_dados += 1
                continue

            # Mapeia o retorno da consulta para os campos do model.
            novos = {
                'endereco': dados.get('rua'),
                'numero': dados.get('numero'),
                'complemento': dados.get('complemento'),
                'bairro': dados.get('bairro'),
                'cidade': dados.get('cidade'),
                'estado': dados.get('estado'),
                'cep': dados.get('cep'),
            }

            # Aqui sobrescrevemos mesmo com o campo preenchido: o valor atual é
            # justamente o endereço errado que viemos corrigir. Campos que a
            # consulta não trouxe permanecem como estão.
            mudancas = []
            for campo in CAMPOS_ENDERECO:
                novo = (novos.get(campo) or '').strip()
                atual = (getattr(condominio, campo) or '').strip()
                if novo and novo != atual:
                    mudancas.append((campo, atual, novo))

            self.stdout.write(f"[{idx}] {cnpj} — {condominio.nome[:45]}")

            if not mudancas:
                self.stdout.write("      nada a alterar")
            else:
                for campo, atual, novo in mudancas:
                    self.stdout.write(f"      {campo:<12} {atual!r} -> {novo!r}")
                alterados += 1

            if aplicar:
                with transaction.atomic():
                    for campo, _atual, novo in mudancas:
                        setattr(condominio, campo, novo)
                    condominio.is_searched = True
                    condominio.save(
                        update_fields=[c for c, _, _ in mudancas] + ['is_searched']
                    )

            time.sleep(sleep)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Fim. Consultados: {consultados} | com alteração: {alterados} | "
                f"sem dados: {sem_dados} | falhas: {falhas}"
            )
        )

        if not aplicar and alterados:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Simulação: nada foi gravado. Repita com --apply para efetivar."))
