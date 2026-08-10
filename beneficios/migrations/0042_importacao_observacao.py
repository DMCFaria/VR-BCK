from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('beneficios', '0041_add_fatura_num_to_faturamentoarquivo'),
    ]

    operations = [
        migrations.AddField(
            model_name='importacao',
            name='observacao',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Texto livre informado pela administradora no envio da importação.',
                verbose_name='Observação',
            ),
        ),
    ]
