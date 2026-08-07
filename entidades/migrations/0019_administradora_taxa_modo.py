from django.db import migrations, models


def backfill_taxa_modo(apps, schema_editor):
    """
    Infere o modo de cobrança das administradoras já cadastradas.

    Até aqui o modo não era gravado — a tela adivinhava lendo as TaxaConfig, e
    classificava como PRODUTO qualquer administradora que tivesse ao menos uma
    configuração, inclusive as cadastradas como CONDOMINIO. Este backfill usa a
    forma dos dados para separar os dois casos:

    - PRODUTO   as TaxaConfig cobrem TODOS os vínculos da administradora e todas
                apontam para um produto específico (é o que o laço
                `vínculos × produtos` da tela gerava)
    - CONDOMINIO existe TaxaConfig, mas cobrindo só parte dos vínculos, ou com
                produto/tipo em branco
    - PADRAO    nenhuma TaxaConfig
    """
    Administradora = apps.get_model('entidades', 'Administradora')
    VinculoCondominio = apps.get_model('entidades', 'VinculoCondominio')
    TaxaConfig = apps.get_model('entidades', 'TaxaConfig')

    for adm in Administradora.objects.all().iterator():
        configs = list(TaxaConfig.objects.filter(vinculo__administradora_id=adm.id))

        if not configs:
            continue  # mantém o default PADRAO

        total_vinculos = VinculoCondominio.objects.filter(administradora_id=adm.id).count()
        vinculos_com_config = {c.vinculo_id for c in configs}
        todas_por_produto = all(c.produto_id for c in configs)

        cobre_todos_vinculos = (
            total_vinculos > 1 and len(vinculos_com_config) == total_vinculos
        )

        if todas_por_produto and cobre_todos_vinculos:
            adm.taxa_modo = 'PRODUTO'
        else:
            adm.taxa_modo = 'CONDOMINIO'

        adm.save(update_fields=['taxa_modo'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('entidades', '0018_add_funcionario_condominio_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='administradora',
            name='taxa_modo',
            field=models.CharField(
                choices=[
                    ('PADRAO', 'Taxa padrão (mesma para todos os condomínios)'),
                    ('PRODUTO', 'Taxa por produto'),
                    ('CONDOMINIO', 'Taxa por condomínio'),
                ],
                default='PADRAO',
                max_length=10,
                verbose_name='Modo de Cobrança da Taxa',
            ),
        ),
        migrations.RunPython(backfill_taxa_modo, noop),
    ]
