from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('beneficios', '0039_add_responsavel_importacao'),
    ]

    operations = [
        migrations.CreateModel(
            name='FaturamentoArquivo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('boleto', 'Boleto'), ('nota_debito', 'Nota de débito'), ('nota_fiscal', 'Nota fiscal')], max_length=30)),
                ('nome_arquivo', models.CharField(max_length=255)),
                ('s3_key', models.CharField(max_length=1000, unique=True)),
                ('url', models.URLField(max_length=1000)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('faturamento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='arquivos_originais', to='beneficios.faturamento', verbose_name='Faturamento')),
            ],
            options={
                'ordering': ['criado_em', 'id'],
                'indexes': [models.Index(fields=['faturamento', 'tipo'], name='idx_fat_arq_tipo')],
            },
        ),
    ]
