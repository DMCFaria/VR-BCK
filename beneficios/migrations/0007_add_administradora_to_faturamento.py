from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('beneficios', '0006_add_administradora_to_importacao'),
    ]

    operations = [
        migrations.AddField(
            model_name='faturamento',
            name='administradora',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='faturamentos', to='entidades.administradora', verbose_name='Administradora'),
        ),
    ]
