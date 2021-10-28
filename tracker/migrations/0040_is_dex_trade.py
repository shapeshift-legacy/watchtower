from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0039_auto_20200923_1417'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='is_dex_trade',
            field=models.BooleanField(default=False, null=False),
        ),
    ]
