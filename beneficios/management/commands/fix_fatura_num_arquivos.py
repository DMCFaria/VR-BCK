import re
from django.core.management.base import BaseCommand
from beneficios.models import FaturamentoArquivo, Boleto


class Command(BaseCommand):
    help = 'Corrige fatura_num em FaturamentoArquivo a partir do nome do arquivo e Boletos existentes'

    def handle(self, *args, **options):
        arquivos_sem_fatura = FaturamentoArquivo.objects.filter(fatura_num='')
        total = arquivos_sem_fatura.count()
        self.stdout.write(f'Processando {total} arquivos sem fatura_num...')

        atualizados = 0
        nao_encontrados = 0

        for arquivo in arquivos_sem_fatura.prefetch_related('faturamento__boletos_rel'):
            fatura_num = self._extrair_fatura_do_nome(arquivo.nome_arquivo)

            if fatura_num:
                # Verificar se existe Boleto com esse fatura_num no mesmo faturamento
                existe_boleto = Boleto.objects.filter(
                    faturamento=arquivo.faturamento,
                    fatura=fatura_num
                ).exists()

                if existe_boleto:
                    arquivo.fatura_num = fatura_num
                    arquivo.save(update_fields=['fatura_num'])
                    atualizados += 1
                    self.stdout.write(f'  Atualizado: {arquivo.nome_arquivo} -> fatura_num={fatura_num}')
                else:
                    self.stdout.write(
                        self.style.WARNING(f'  Aviso: {arquivo.nome_arquivo} -> fatura_num={fatura_num} '
                                           f'(Boleto não encontrado no faturamento {arquivo.faturamento_id})')
                    )
                    # Mesmo assim salva, pois o número veio do nome do arquivo
                    arquivo.fatura_num = fatura_num
                    arquivo.save(update_fields=['fatura_num'])
                    atualizados += 1
            else:
                # Tentar extrair do nome e procurar no faturamento
                candidatos = re.findall(r'\d{6,}', arquivo.nome_arquivo)
                preenchido = False
                for candidato in candidatos:
                    existe = Boleto.objects.filter(
                        faturamento=arquivo.faturamento,
                        fatura=candidato
                    ).exists()
                    if existe:
                        arquivo.fatura_num = candidato
                        arquivo.save(update_fields=['fatura_num'])
                        atualizados += 1
                        self.stdout.write(f'  Atualizado (fallback): {arquivo.nome_arquivo} -> fatura_num={candidato}')
                        preenchido = True
                        break

                if not preenchido:
                    nao_encontrados += 1
                    self.stdout.write(
                        self.style.WARNING(f'  Não encontrado: {arquivo.nome_arquivo} (faturamento={arquivo.faturamento_id})')
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nConcluído: {atualizados} atualizados, {nao_encontrados} não encontrados'
            )
        )

    def _extrair_fatura_do_nome(self, nome_arquivo):
        """Extrai número de fatura do nome do arquivo. Ex: BOLETO_174668.pdf -> 174668"""
        match = re.search(r'(\d{6,})', nome_arquivo)
        return match.group(1) if match else None
