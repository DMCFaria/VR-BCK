"""
Ressincroniza os boletos de um faturamento a partir do FedHub, sem reenviar
PDFs.

Uso:
    python manage.py sincronizar_boletos 447
    python manage.py sincronizar_boletos 447 --fatura 175826
    python manage.py sincronizar_boletos 447 --dry-run

O número da fatura é descoberto pelo FaturamentoArquivo (tipo boleto) do
faturamento; use --fatura para forçar. Reaproveita exatamente a mesma gravação
da task `processar_faturamento` (upload/boletos_sync.py).
"""
from django.core.management.base import BaseCommand, CommandError

from beneficios.models import Faturamento, FaturamentoArquivo, Boleto
from core.fedhub.services.fedhub_service import FedhubService
from upload.boletos_sync import gravar_boletos_fedhub


class Command(BaseCommand):
    help = "Ressincroniza os boletos de um faturamento a partir do FedHub (sem reenviar PDFs)."

    def add_arguments(self, parser):
        parser.add_argument('faturamento_id', type=int)
        parser.add_argument('--fatura', help="Número da fatura no FedHub (padrão: o do PDF de boleto do faturamento).")
        parser.add_argument('--dry-run', action='store_true', help="Só consulta o FedHub e mostra o que seria gravado.")

    def handle(self, *args, **options):
        fat_id = options['faturamento_id']
        try:
            faturamento = Faturamento.objects.select_related('importacao', 'administradora').get(id=fat_id)
        except Faturamento.DoesNotExist:
            raise CommandError(f"Faturamento {fat_id} não encontrado.")

        fatura_num = options.get('fatura')
        if not fatura_num:
            arquivo = (
                FaturamentoArquivo.objects
                .filter(faturamento=faturamento, tipo='boleto')
                .exclude(fatura_num='')
                .order_by('-criado_em')
                .first()
            )
            fatura_num = arquivo.fatura_num if arquivo else None
        if not fatura_num:
            raise CommandError(
                "Não foi possível descobrir o número da fatura (nenhum FaturamentoArquivo de boleto com fatura_num). "
                "Informe com --fatura."
            )

        antes = Boleto.objects.filter(faturamento=faturamento).count()
        self.stdout.write(
            f"Faturamento {faturamento.id} | importação {faturamento.importacao_id} | "
            f"adm {faturamento.administradora_id} | status {faturamento.status} | "
            f"fatura {fatura_num} | boletos locais antes: {antes}"
        )

        boletos_data = FedhubService().buscar_todos_boletos_por_fatura(fatura_num)
        if not isinstance(boletos_data, list):
            boletos_data = [boletos_data] if boletos_data else []
        self.stdout.write(f"FedHub devolveu {len(boletos_data)} item(ns) para a fatura {fatura_num}.")

        if not boletos_data:
            raise CommandError(
                "FedHub não devolveu boletos para essa fatura. Confira no ERP se a fatura existe e tem boletos gerados."
            )

        sem_doc = [b for b in boletos_data if not b.get('documento')]
        if sem_doc:
            self.stdout.write(self.style.WARNING(
                f"{len(sem_doc)} item(ns) SEM 'documento' — serão ignorados. Chaves do primeiro: {sorted(sem_doc[0].keys())}"
            ))

        if options['dry_run']:
            for b in boletos_data:
                self.stdout.write(
                    f"  - doc={b.get('documento')} cnpj={b.get('cnpj_cobrado')} valor={b.get('valor')} "
                    f"venc={b.get('vencimento')} baixa={b.get('baixa')} status={b.get('status')}"
                )
            self.stdout.write(self.style.NOTICE("Dry-run: nada gravado."))
            return

        stats = gravar_boletos_fedhub(faturamento, fatura_num, boletos_data)
        depois = Boleto.objects.filter(faturamento=faturamento).count()

        if stats['gravados'] == 0:
            raise CommandError(
                f"Nenhum boleto gravado ({stats['sem_documento']} sem 'documento' de {stats['total']})."
            )

        self.stdout.write(self.style.SUCCESS(
            f"OK: {stats['gravados']}/{stats['total']} boletos gravados para a fatura {fatura_num}. "
            f"Boletos locais do faturamento: {antes} → {depois}."
        ))
