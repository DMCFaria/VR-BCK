from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('beneficios', '0027_add_data_recebimento'),
    ]

    operations = [
        migrations.AlterField(
            model_name='importacao',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pendente'),
                    ('PROCESSING', 'Processando'),
                    ('AGUARDANDO_FATURAMENTO', 'Aguardando Faturamento'),
                    ('FATURADO', 'Faturado'),
                    ('COMPRADO', 'Comprado'),
                    ('CANCELADO', 'Cancelado'),
                    ('COMPLETED', 'Concluída'),
                    ('FAILED', 'Falhou'),
                ],
                db_index=True,
                default='PENDING',
                max_length=30,
                verbose_name='Status',
            ),
        ),
    ]
