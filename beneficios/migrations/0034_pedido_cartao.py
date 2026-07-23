# Generated manually

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('beneficios', '0033_auto_20260722_1619'),
        ('entidades', '0016_administradora_bairro_administradora_cep_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PedidoCartao',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('tipo_pedido', models.CharField(choices=[('NOVO', 'Cartão Novo'), ('SEGUNDA_VIA', 'Segunda Via')], max_length=20, verbose_name='Tipo de Pedido')),
                ('nome_completo', models.CharField(max_length=255, verbose_name='Nome Completo')),
                ('cpf', models.CharField(max_length=14, verbose_name='CPF')),
                ('data_nascimento', models.DateField(verbose_name='Data de Nascimento')),
                ('produto', models.CharField(max_length=100, verbose_name='Produto')),
                ('nome_condominio', models.CharField(max_length=255, verbose_name='Nome do Condomínio')),
                ('cep', models.CharField(blank=True, max_length=10, null=True, verbose_name='CEP')),
                ('logradouro', models.CharField(blank=True, max_length=255, null=True, verbose_name='Logradouro')),
                ('numero', models.CharField(blank=True, max_length=20, null=True, verbose_name='Número')),
                ('complemento', models.CharField(blank=True, max_length=100, null=True, verbose_name='Complemento')),
                ('bairro', models.CharField(blank=True, max_length=100, null=True, verbose_name='Bairro')),
                ('cidade', models.CharField(blank=True, max_length=100, null=True, verbose_name='Cidade')),
                ('estado', models.CharField(blank=True, max_length=2, null=True, verbose_name='UF')),
                ('valor', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Valor')),
                ('status', models.CharField(choices=[('PENDENTE', 'Pendente'), ('EM_ANALISE', 'Em Análise'), ('APROVADO', 'Aprovado'), ('ENVIADO', 'Enviado'), ('RECUSADO', 'Recusado'), ('CANCELADO', 'Cancelado')], default='PENDENTE', max_length=20, verbose_name='Status')),
                ('observacao', models.TextField(blank=True, null=True, verbose_name='Observação')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
                ('administradora', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='entidades.administradora', verbose_name='Administradora')),
                ('criado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Criado por')),
            ],
            options={
                'verbose_name': 'Pedido de Cartão',
                'verbose_name_plural': 'Pedidos de Cartão',
                'ordering': ['-created_at'],
            },
        ),
    ]
