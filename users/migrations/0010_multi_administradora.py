import django.db.models.deletion
from django.db import migrations, models


def forwards_copy_administradora(apps, schema_editor):
    """Copia dados da FK administradora para M2M + administradora_ativa."""
    User = apps.get_model('users', 'CustomUser')
    for user in User.objects.exclude(administradora__isnull=True).select_related('administradora'):
        # Adiciona à M2M
        user.administradoras.add(user.administradora)
        # Define como ativa
        user.administradora_ativa = user.administradora
        user.save(update_fields=['administradora_ativa'])


def reverse_copy_administradora(apps, schema_editor):
    """Reverte: copia administradora_ativa de volta para FK (se existisse)."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('entidades', '0012_idx_importacao_adm_data'),
        ('users', '0009_alter_customuser_tipo'),
    ]

    operations = [
        # 1. Adicionar novos campos PRIMEIRO (antes de remover o antigo)
        migrations.AddField(
            model_name='customuser',
            name='administradora_ativa',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='usuarios_ativos',
                to='entidades.administradora',
                verbose_name='Administradora Ativa'
            ),
        ),
        migrations.AddField(
            model_name='customuser',
            name='administradoras',
            field=models.ManyToManyField(
                blank=True,
                related_name='usuarios',
                to='entidades.administradora',
                verbose_name='Administradoras'
            ),
        ),
        # 2. Migrar dados da FK antiga para os novos campos
        migrations.RunPython(
            forwards_copy_administradora,
            reverse_copy_administradora,
        ),
        # 3. Remover FK antiga DEPOIS da migração de dados
        migrations.RemoveField(
            model_name='customuser',
            name='administradora',
        ),
    ]
