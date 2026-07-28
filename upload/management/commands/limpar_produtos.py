"""
Management command para limpar a tabela Produto, restando apenas
os 6 códigos canônicos do template VR padrão.

Uso:
    python manage.py limpar_produtos              # dry-run (mostra o que seria feito)
    python manage.py limpar_produtos --apply      # aplica as mudanças
    python manage.py limpar_produtos --apply --backup  # exporta CSV antes de aplicar
"""

import csv
import os
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from beneficios.models import Produto, MovimentacaoBeneficio


# ============================================================
# Produtos canônicos
# ============================================================
PRODUTOS_CANONICOS = {
    '27':  {'nome': 'VR Alimentação',            'tipo': 'ALIMENTACAO',    'coluna': 'K'},
    '28':  {'nome': 'VR Auto',                   'tipo': 'AUTO',           'coluna': 'L'},
    '201': {'nome': 'VR Alimentação Cesta',      'tipo': 'BOAS_FESTAS',    'coluna': 'N'},
    '202': {'nome': 'VR Boas Festas',            'tipo': 'BOAS_FESTAS',    'coluna': 'O'},
    '204': {'nome': 'VR Auxílio Alimentação',    'tipo': 'ALIMENTACAO',    'coluna': 'P'},
    '207': {'nome': 'VR Refeição',               'tipo': 'REFEICAO',       'coluna': 'J'},
}

# Mapeamento tipo antigo → código canônico
MAPEAMENTO_TIPO_PARA_CODIGO = {
    'ALIMENTACAO':        '27',
    'AUTO':               '28',
    'REFEICAO':           '207',
    'MULTI_HOME_OFFICE':  '207',
    'BOAS_FESTAS':        '202',
    'MULTI_ALIMENTACAO':  '27',
    'MULTI_VR_VA':        '207',
    'MULTI_REFEICAO':     '207',
    'MULTI_MOBILIDADE':   '28',
}

CODIGO_PADRAO = '207'


class Command(BaseCommand):
    help = 'Limpa a tabela Produto, restando apenas os 6 códigos canônicos do VR.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Aplica as mudanças (sem esta flag, é dry-run).',
        )
        parser.add_argument(
            '--backup',
            action='store_true',
            help='Exporta CSV de backup antes de aplicar (requer --apply).',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        backup = options['backup']

        # ===========================================================
        # 1. Coletar dados atuais
        # ===========================================================
        todos_produtos = list(Produto.objects.all().order_by('codigo_produto'))
        codigos_canonicos = set(PRODUTOS_CANONICOS.keys())

        produtos_canonicos_existentes = [p for p in todos_produtos if p.codigo_produto in codigos_canonicos]
        produtos_nao_canonicos = [p for p in todos_produtos if p.codigo_produto not in codigos_canonicos]

        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(self.style.WARNING('LIMPEZA DA TABELA PRODUTO'))
        self.stdout.write(self.style.WARNING('=' * 70))

        # ===========================================================
        # 2. Mostrar produtos canônicos atuais
        # ===========================================================
        self.stdout.write(f'\nProdutos canônicos existentes: {len(produtos_canonicos_existentes)}')
        for p in produtos_canonicos_existentes:
            info = PRODUTOS_CANONICOS.get(p.codigo_produto, {})
            coluna = info.get('coluna', '?')
            self.stdout.write(f'  [{coluna}] {p.codigo_produto} - {p.nome} ({p.tipo})')

        # ===========================================================
        # 3. Mostrar produtos que serão removidos
        # ===========================================================
        self.stdout.write(f'\nProdutos que serão REMOVIDOS: {len(produtos_nao_canonicos)}')
        total_mov_afetadas = 0
        mapeamento_preview = {}

        for p in produtos_nao_canonicos:
            tipo = (p.tipo or '').strip().upper()
            codigo_canonico = MAPEAMENTO_TIPO_PARA_CODIGO.get(tipo, CODIGO_PADRAO)
            mapeamento_preview[p.codigo_produto] = codigo_canonico

            qtd_mov = MovimentacaoBeneficio.objects.filter(
                produto_codigo=p.codigo_produto
            ).count()
            total_mov_afetadas += qtd_mov

            self.stdout.write(
                f'  {p.codigo_produto:>10} | {p.nome[:45]:<45} | '
                f'{(p.tipo or "None"):<20} → {codigo_canonico} '
                f'({qtd_mov} movimentações)'
            )

        # ===========================================================
        # 4. Resumo de movimentações
        # ===========================================================
        self.stdout.write(f'\nMovimentações que serão reatribuídas: {total_mov_afetadas}')

        # ===========================================================
        # 5. Verificar duplicatas
        # ===========================================================
        from django.db.models import Count
        duplicatas = (
            Produto.objects
            .values('codigo_produto')
            .annotate(cnt=Count('codigo_produto'))
            .filter(cnt__gt=1)
        )
        if duplicatas:
            self.stdout.write(self.style.WARNING(f'\nDuplicatas encontradas:'))
            for d in duplicatas:
                self.stdout.write(
                    f'  Código {d["codigo_produto"]}: {d["cnt"]} registros '
                    f'(manterá o primeiro, reatribuirá e deletará os demais)'
                )

        # ===========================================================
        # 6. Dry-run ou Apply
        # ===========================================================
        if not apply:
            self.stdout.write(self.style.WARNING(
                '\n>>> DRY-RUN: Nenhuma alteração foi feita.\n'
                '>>> Para aplicar, execute com --apply:\n'
                '>>>   python manage.py limpar_produtos --apply'
            ))
            return

        # ===========================================================
        # 7. Backup (opcional)
        # ===========================================================
        if backup:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join('backups', 'limpeza_produtos')
            os.makedirs(backup_dir, exist_ok=True)

            # Backup de Produtos
            prod_file = os.path.join(backup_dir, f'produtos_backup_{timestamp}.csv')
            with open(prod_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['codigo_produto', 'nome', 'tipo', 'fornecedora', 'cod_fornecedora'])
                for p in todos_produtos:
                    writer.writerow([
                        p.codigo_produto, p.nome, p.tipo,
                        p.fornecedora, p.cod_fornecedora
                    ])
            self.stdout.write(self.style.SUCCESS(f'Backup de produtos: {prod_file}'))

            # Backup de Movimentações afetadas
            mov_file = os.path.join(backup_dir, f'movimentacoes_backup_{timestamp}.csv')
            mov_ids = MovimentacaoBeneficio.objects.filter(
                produto_codigo__in=[p.codigo_produto for p in produtos_nao_canonicos]
            ).values_list('id', flat=True)
            with open(mov_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'id', 'empresa_cnpj_id', 'funcionario_cpf_id',
                    'produto_codigo_antigo', 'data_competencia',
                    'valor_beneficio', 'quantidade_dias'
                ])
                for mov in MovimentacaoBeneficio.objects.filter(id__in=mov_ids):
                    writer.writerow([
                        mov.id, mov.empresa_cnpj_id, mov.funcionario_cpf_id,
                        mov.produto_codigo_id, mov.data_competencia,
                        mov.valor_beneficio, mov.quantidade_dias
                    ])
            self.stdout.write(self.style.SUCCESS(f'Backup de movimentações: {mov_file}'))

        # ===========================================================
        # 8. Aplicar mudanças
        # ===========================================================
        self.stdout.write(self.style.WARNING('\nAplicando mudanças...'))

        with transaction.atomic():
            movimentacoes_atualizadas = 0
            produtos_deletados = 0
            duplicatas_resolvidas = 0

            # 8a. Criar canônicos que não existem
            for codigo, info in PRODUTOS_CANONICOS.items():
                Produto.objects.get_or_create(
                    codigo_produto=codigo,
                    defaults={'nome': info['nome'], 'tipo': info['tipo']},
                )

            # 8b. Mapear e reatribuir (com soma em caso de conflito)
            for produto in produtos_nao_canonicos:
                tipo = (produto.tipo or '').strip().upper()
                codigo_canonico = MAPEAMENTO_TIPO_PARA_CODIGO.get(tipo, CODIGO_PADRAO)

                # Garantir que o canônico exista
                info_canonico = PRODUTOS_CANONICOS[codigo_canonico]
                Produto.objects.get_or_create(
                    codigo_produto=codigo_canonico,
                    defaults={'nome': info_canonico['nome'], 'tipo': info_canonico['tipo']},
                )

                # Buscar movimentações do produto antigo
                movs_antigas = MovimentacaoBeneficio.objects.filter(
                    produto_codigo=produto.codigo_produto
                )

                for mov in movs_antigas:
                    # Verificar se já existe movimentação canônica com a mesma chave
                    conflito = MovimentacaoBeneficio.objects.filter(
                        importacao=mov.importacao,
                        empresa_cnpj=mov.empresa_cnpj,
                        funcionario_cpf=mov.funcionario_cpf,
                        produto_codigo=codigo_canonico,
                        data_competencia=mov.data_competencia,
                    ).first()

                    if conflito:
                        # Somar valor e deletar a antiga
                        conflito.valor_beneficio += mov.valor_beneficio
                        conflito.quantidade_dias += mov.quantidade_dias
                        conflito.save(update_fields=['valor_beneficio', 'quantidade_dias'])
                        mov.delete()
                        movimentacoes_atualizadas += 1
                    else:
                        # Reatribuir para o canônico
                        mov.produto_codigo_id = codigo_canonico
                        mov.save(update_fields=['produto_codigo_id'])
                        movimentacoes_atualizadas += 1

                # Deletar produto antigo
                Produto.objects.filter(codigo_produto=produto.codigo_produto).delete()
                produtos_deletados += 1

            # 8c. Resolver duplicatas (com soma em caso de conflito)
            for codigo in codigos_canonicos:
                objs = list(Produto.objects.filter(codigo_produto=codigo).order_by('codigo_produto'))
                if len(objs) > 1:
                    manter = objs[0]
                    for duplicata in objs[1:]:
                        movs_dup = MovimentacaoBeneficio.objects.filter(
                            produto_codigo=duplicata.codigo_produto
                        )
                        for mov in movs_dup:
                            conflito = MovimentacaoBeneficio.objects.filter(
                                importacao=mov.importacao,
                                empresa_cnpj=mov.empresa_cnpj,
                                funcionario_cpf=mov.funcionario_cpf,
                                produto_codigo=manter.codigo_produto,
                                data_competencia=mov.data_competencia,
                            ).first()
                            if conflito:
                                conflito.valor_beneficio += mov.valor_beneficio
                                conflito.quantidade_dias += mov.quantidade_dias
                                conflito.save(update_fields=['valor_beneficio', 'quantidade_dias'])
                                mov.delete()
                            else:
                                mov.produto_codigo_id = manter.codigo_produto
                                mov.save(update_fields=['produto_codigo_id'])
                            movimentacoes_atualizadas += 1
                        duplicata.delete()
                        duplicatas_resolvidas += 1

        # ===========================================================
        # 9. Resumo final
        # ===========================================================
        total_produtos_final = Produto.objects.count()
        total_mov_final = MovimentacaoBeneficio.objects.count()

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('RESUMO FINAL'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'Produtos deletados:          {produtos_deletados}')
        self.stdout.write(f'Duplicatas resolvidas:       {duplicatas_resolvidas}')
        self.stdout.write(f'Movimentações reatribuídas:  {movimentacoes_atualizadas}')
        self.stdout.write(f'Total de produtos:           {total_produtos_final}')
        self.stdout.write(f'Total de movimentações:      {total_mov_final}')
        self.stdout.write(self.style.SUCCESS('=' * 70))

        # Listar produtos restantes
        self.stdout.write('\nProdutos restantes:')
        for p in Produto.objects.all().order_by('codigo_produto'):
            info = PRODUTOS_CANONICOS.get(p.codigo_produto, {})
            coluna = info.get('coluna', '?')
            self.stdout.write(f'  [{coluna}] {p.codigo_produto} - {p.nome} ({p.tipo})')
