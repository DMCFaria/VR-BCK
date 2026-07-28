"""
Migration de dados: limpa a tabela Produto, restando apenas os 6 códigos
canônicos do template VR padrão.

Códigos canônicos:
  27  = VR Alimentação           (ALIMENTACAO)
  28  = VR Auto                  (AUTO)
  201 = VR Alimentação Cesta     (BOAS_FESTAS)
  202 = VR Boas Festas           (BOAS_FESTAS)
  204 = VR Auxílio Alimentação   (ALIMENTACAO)
  207 = VR Refeição              (REFEICAO)

Produtos com outros códigos são mapeados para o canônico correspondente
pelo campo 'tipo'. MovimentacaoBeneficio são reatribuidas ao produto
canônico. Produtos antigos são deletados permanentemente.
"""

from django.db import migrations

# ============================================================
# Produtos canônicos: código → {nome, tipo}
# ============================================================
PRODUTOS_CANONICOS = {
    '27':  {'nome': 'VR Alimentação',            'tipo': 'ALIMENTACAO'},
    '28':  {'nome': 'VR Auto',                   'tipo': 'AUTO'},
    '201': {'nome': 'VR Alimentação Cesta',      'tipo': 'BOAS_FESTAS'},
    '202': {'nome': 'VR Boas Festas',            'tipo': 'BOAS_FESTAS'},
    '204': {'nome': 'VR Auxílio Alimentação',    'tipo': 'ALIMENTACAO'},
    '207': {'nome': 'VR Refeição',               'tipo': 'REFEICAO'},
}

# ============================================================
# Mapeamento de tipo do produto antigo → código canônico
# ============================================================
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

# Código padrão para tipo None/vazio ou não mapeado
CODIGO_PADRAO = '207'


def forward(apps, schema_editor):
    Produto = apps.get_model('beneficios', 'Produto')
    Movimentacao = apps.get_model('beneficios', 'MovimentacaoBeneficio')

    # ----------------------------------------------------------
    # 1. Garantir que os 6 produtos canônicos existam
    # ----------------------------------------------------------
    canonicos_criados = 0
    for codigo, info in PRODUTOS_CANONICOS.items():
        obj, created = Produto.objects.get_or_create(
            codigo_produto=codigo,
            defaults={'nome': info['nome'], 'tipo': info['tipo']},
        )
        if created:
            canonicos_criados += 1
        elif obj.tipo != info['tipo']:
            obj.tipo = info['tipo']
            obj.save(update_fields=['tipo'])

    # ----------------------------------------------------------
    # 2. Coletar todos os códigos canônicos já existentes
    # (pode haver duplicatas criadas por bug anterior)
    # ----------------------------------------------------------
    codigos_canonicos = set(PRODUTOS_CANONICOS.keys())

    # ----------------------------------------------------------
    # 3. Encontrar produtos não canônicos
    # ----------------------------------------------------------
    todos_produtos = list(Produto.objects.all().order_by('codigo_produto'))
    produtos_nao_canonicos = [p for p in todos_produtos if p.codigo_produto not in codigos_canonicos]

    # ----------------------------------------------------------
    # 4. Mapear cada produto não canônico para o canônico
    # ----------------------------------------------------------
    movimentacoes_atualizadas = 0
    produtos_deletados = 0
    erros = []

    # Dicionário de cache: código antigo → código canônico
    cache_mapeamento = {}

    for produto in produtos_nao_canonicos:
        codigo_antigo = produto.codigo_produto

        # Determinar código canônico pelo tipo
        tipo = (produto.tipo or '').strip().upper()
        codigo_canonico = MAPEAMENTO_TIPO_PARA_CODIGO.get(tipo, CODIGO_PADRAO)

        cache_mapeamento[codigo_antigo] = codigo_canonico

        # Garantir que o canônico exista
        info_canonico = PRODUTOS_CANONICOS[codigo_canonico]
        Produto.objects.get_or_create(
            codigo_produto=codigo_canonico,
            defaults={'nome': info_canonico['nome'], 'tipo': info_canonico['tipo']},
        )

        # Reatribuir movimentações (com soma em caso de conflito)
        movs_antigas = Movimentacao.objects.filter(produto_codigo=codigo_antigo)
        for mov in movs_antigas:
            conflito = Movimentacao.objects.filter(
                importacao=mov.importacao,
                empresa_cnpj=mov.empresa_cnpj,
                funcionario_cpf=mov.funcionario_cpf,
                produto_codigo=codigo_canonico,
                data_competencia=mov.data_competencia,
            ).first()

            if conflito:
                conflito.valor_beneficio += mov.valor_beneficio
                conflito.quantidade_dias += mov.quantidade_dias
                conflito.save(update_fields=['valor_beneficio', 'quantidade_dias'])
                mov.delete()
            else:
                mov.produto_codigo_id = codigo_canonico
                mov.save(update_fields=['produto_codigo_id'])
            movimentacoes_atualizadas += 1

        # Deletar o produto antigo
        Produto.objects.filter(codigo_produto=codigo_antigo).delete()
        produtos_deletados += 1

    # ----------------------------------------------------------
    # 5. Resolver duplicatas de código canônico
    # (manter o primeiro, reatribuir com soma e deletar os duplicados)
    # ----------------------------------------------------------
    duplicatas_resolvidas = 0
    for codigo in codigos_canonicos:
        objs = list(Produto.objects.filter(codigo_produto=codigo).order_by('codigo_produto'))
        if len(objs) > 1:
            manter = objs[0]
            for duplicata in objs[1:]:
                movs_dup = Movimentacao.objects.filter(produto_codigo=duplicata.codigo_produto)
                for mov in movs_dup:
                    conflito = Movimentacao.objects.filter(
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

    # ----------------------------------------------------------
    # 6. Resumo
    # ----------------------------------------------------------
    total_produtos = Produto.objects.count()
    total_mov = Movimentacao.objects.count()

    print("=" * 60)
    print("LIMPEZA DA TABELA PRODUTO - RESUMO")
    print("=" * 60)
    print(f"Produtos canônicos criados:  {canonicos_criados}")
    print(f"Produtos não canônicos:      {len(produtos_nao_canonicos)}")
    print(f"Produtos deletados:          {produtos_deletados}")
    print(f"Duplicatas resolvidas:       {duplicatas_resolvidas}")
    print(f"Movimentações reatribuídas:  {movimentacoes_atualizadas}")
    print(f"Total de produtos restantes: {total_produtos}")
    print(f"Total de movimentações:      {total_mov}")
    print("=" * 60)

    if cache_mapeamento:
        print("\nMapeamento aplicado (antigo → canônico):")
        for antigo, canonico in sorted(cache_mapeamento.items()):
            print(f"  {antigo} → {canonico}")
        print()


def reverse(apps, schema_editor):
    print("ATENÇÃO: Esta migration é irreversível (DELETE permanente).")
    print("Para reverter, restaure o banco de backup.")


class Migration(migrations.Migration):

    dependencies = [
        ('beneficios', '0035_alter_boleto_campos'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
