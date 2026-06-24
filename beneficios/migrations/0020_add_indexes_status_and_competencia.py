from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('beneficios', '0019_produto_cod_fornecedora_produto_fornecedora_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='importacao',
            name='status',
            field=models.CharField(choices=[('PENDING', 'Pendente'), ('PROCESSING', 'Processando'), ('AGUARDANDO_FATURAMENTO', 'Aguardando Faturamento'), ('FATURADO', 'Faturado'), ('CANCELADO', 'Cancelado'), ('COMPLETED', 'Concluída'), ('FAILED', 'Falhou')], db_index=True, default='PENDING', max_length=30, verbose_name='Status'),
        ),
        migrations.AlterField(
            model_name='movimentacaobeneficio',
            name='data_competencia',
            field=models.DateField(db_index=True, verbose_name='Data de Competência'),
        ),
        migrations.AddIndex(
            model_name='importacao',
            index=models.Index(fields=['administradora', 'status'], name='idx_importacao_adm_status'),
        ),
    ]
