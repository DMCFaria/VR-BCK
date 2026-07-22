import logging
import re
import time

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Consulta CNPJs de todos os condomínios e atualiza nome/endereço via BigDataCorp."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.5,
            help="Tempo de espera entre consultas (em segundos). Padrão: 0.5",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limite de condomínios a consultar. Padrão: todos.",
        )
        parser.add_argument(
            "--apenas-vazios",
            action="store_true",
            help="Consulta apenas condomínios com endereço vazio.",
        )
        parser.add_argument(
            "--sobrescrever",
            action="store_true",
            help="Sobrescreve endereço mesmo que já esteja preenchido.",
        )

    def handle(self, *args, **options):
        from entidades.models import Condominio
        from upload.services import CNPJConsultaService
        from django.conf import settings

        sleep = options["sleep"]
        limit = options["limit"]
        apenas_vazios = options["apenas_vazios"]
        sobrescrever = options["sobrescrever"]

        if not getattr(settings, "BIGDATA_ACCESS_TOKEN", "") or not getattr(settings, "BIGDATA_TOKEN_ID", ""):
            self.stderr.write(self.style.ERROR("BIGDATA_ACCESS_TOKEN ou BIGDATA_TOKEN_ID não configurados."))
            return

        qs = Condominio.objects.all()
        if apenas_vazios:
            qs = qs.filter(endereco__isnull=True) | qs.filter(endereco="")
        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(f"Total de condomínios a consultar: {total}")

        pesquisados = 0
        atualizados = 0
        falhas = 0

        for idx, condominio in enumerate(qs.iterator(), start=1):
            cnpj = re.sub(r"\D", "", str(condominio.cnpj or ""))
            if len(cnpj) != 14:
                self.stdout.write(f"[{idx}/{total}] CNPJ inválido: {condominio.cnpj}")
                continue

            try:
                dados = CNPJConsultaService.consultar(cnpj, fonte="bigdatacorp_addresses")
                pesquisados += 1

                if not dados:
                    self.stdout.write(f"[{idx}/{total}] Sem dados para {cnpj}")
                    falhas += 1
                    continue

                campos_atualizados = []

                if dados.get("razao_social") and condominio.nome != dados["razao_social"]:
                    condominio.nome = dados["razao_social"]
                    campos_atualizados.append("nome")

                if dados.get("rua") and (sobrescrever or not condominio.endereco):
                    condominio.endereco = dados["rua"]
                    campos_atualizados.append("endereco")
                if dados.get("numero") and (sobrescrever or not condominio.numero):
                    condominio.numero = dados["numero"]
                    campos_atualizados.append("numero")
                if dados.get("complemento") and (sobrescrever or not condominio.complemento):
                    condominio.complemento = dados["complemento"]
                    campos_atualizados.append("complemento")
                if dados.get("bairro") and (sobrescrever or not condominio.bairro):
                    condominio.bairro = dados["bairro"]
                    campos_atualizados.append("bairro")
                if dados.get("cidade") and (sobrescrever or not condominio.cidade):
                    condominio.cidade = dados["cidade"]
                    campos_atualizados.append("cidade")
                if dados.get("estado") and (sobrescrever or not condominio.estado):
                    condominio.estado = dados["estado"]
                    campos_atualizados.append("estado")
                if dados.get("cep") and (sobrescrever or not condominio.cep):
                    condominio.cep = dados["cep"]
                    campos_atualizados.append("cep")

                condominio.is_searched = True
                condominio.save(update_fields=campos_atualizados + ["is_searched"])
                atualizados += 1

                self.stdout.write(
                    f"[{idx}/{total}] {cnpj} atualizado: {campos_atualizados}"
                )

                time.sleep(sleep)

            except Exception as e:
                logger.exception(f"Erro ao consultar CNPJ {cnpj}: {e}")
                self.stdout.write(f"[{idx}/{total}] ERRO ao consultar {cnpj}: {e}")
                falhas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Finalizado. Pesquisados: {pesquisados}, atualizados: {atualizados}, falhas: {falhas}"
            )
        )
