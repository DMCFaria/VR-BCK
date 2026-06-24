from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('upload', '0010_add_status_aguardando_faturamento_fileupload'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fileupload',
            name='process_status',
            field=models.CharField(choices=[('PENDING', 'Pendente de Processamento'), ('PARSED', 'Dados Extraídos, Pendente de Confirmação'), ('AGUARDANDO_FATURAMENTO', 'Aguardando Faturamento'), ('COMPLETED', 'Processamento Finalizado'), ('FAILED', 'Falha no Processamento')], db_index=True, default='PENDING', max_length=30, verbose_name='Status do Processamento'),
        ),
    ]
