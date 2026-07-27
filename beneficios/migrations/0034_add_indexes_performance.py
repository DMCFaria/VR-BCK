from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('beneficios', '0033_auto_20260722_1619'),
    ]

    operations = [
        # MovimentacaoBeneficio indexes
        migrations.AddIndex(
            model_name='movimentacaobeneficio',
            index=models.Index(fields=['importacao'], name='idx_mov_importacao'),
        ),
        migrations.AddIndex(
            model_name='movimentacaobeneficio',
            index=models.Index(fields=['empresa_cnpj'], name='idx_mov_empresa'),
        ),
        migrations.AddIndex(
            model_name='movimentacaobeneficio',
            index=models.Index(fields=['funcionario_cpf'], name='idx_mov_funcionario'),
        ),
        migrations.AddIndex(
            model_name='movimentacaobeneficio',
            index=models.Index(fields=['importacao', 'empresa_cnpj'], name='idx_mov_imp_emp'),
        ),
        # Boleto indexes
        migrations.AddIndex(
            model_name='boleto',
            index=models.Index(fields=['faturamento'], name='idx_boleto_fat'),
        ),
        migrations.AddIndex(
            model_name='boleto',
            index=models.Index(fields=['vencimento'], name='idx_boleto_venc'),
        ),
        # Faturamento indexes
        migrations.AddIndex(
            model_name='faturamento',
            index=models.Index(fields=['importacao'], name='idx_fat_importacao'),
        ),
        migrations.AddIndex(
            model_name='faturamento',
            index=models.Index(fields=['administradora'], name='idx_fat_adm'),
        ),
    ]
