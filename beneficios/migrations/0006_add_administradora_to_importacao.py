from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('beneficios', '0005_faturamento_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='importacao',
            name='administradora',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='importacoes', to='entidades.administradora', verbose_name='Administradora'),
        ),
    ]
