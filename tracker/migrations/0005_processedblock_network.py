# Generated by Django 2.0.7 on 2018-08-21 08:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0004_xpub_network'),
    ]

    operations = [
        migrations.AddField(
            model_name='processedblock',
            name='network',
            field=models.CharField(choices=[('BTC', 'BTC'), ('BCH', 'BCH'), ('LTC', 'LTC'), ('DOGE', 'DOGE'), ('DASH', 'DASH')], default='BTC', max_length=100),
            preserve_default=False,
        ),
    ]
