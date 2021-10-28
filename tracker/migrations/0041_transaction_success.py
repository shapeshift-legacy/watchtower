from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0040_is_dex_trade'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='success',
            field=models.BooleanField(default=True, null=False),
        ),
    ]
