from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('beneficios', '0034_add_indexes_performance'),
    ]

    operations = [
        migrations.AlterField(
            model_name='boleto',
            name='cnpj_cobrado',
            field=models.CharField(max_length=14, verbose_name='CNPJ Cobrado', null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='boleto',
            name='status',
            field=models.CharField(max_length=1, verbose_name='Status', null=True, blank=True),
        ),
    ]
