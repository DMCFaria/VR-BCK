from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entidades', '0017_remove_taxaconfig_unique_vinculo_produto_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='funcionario',
            index=models.Index(fields=['condominio'], name='idx_func_condo'),
        ),
    ]
