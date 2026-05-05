from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_customuser_administradora_alter_customuser_tipo'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='empresa',
            field=models.CharField(max_length=100, blank=True, null=True),
        ),
    ]