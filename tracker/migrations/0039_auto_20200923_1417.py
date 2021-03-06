# Generated by Django 2.0.7 on 2020-09-23 20:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0038_enable_bal_comp'),
    ]

    operations = [
        migrations.AlterField(
            model_name='account',
            name='network',
            field=models.CharField(choices=[('BTC', 'BTC'), ('BCH', 'BCH'), ('LTC', 'LTC'), ('DOGE', 'DOGE'), ('DASH', 'DASH'), ('DGB', 'DGB'), ('ETH', 'ETH'), ('ATOM', 'ATOM'), ('BNB', 'BNB'), ('EOS', 'EOS'), ('FIO', 'FIO'), ('XRP', 'XRP')], max_length=100),
        ),
        migrations.AlterField(
            model_name='accountbalance',
            name='network',
            field=models.CharField(choices=[('BTC', 'BTC'), ('BCH', 'BCH'), ('LTC', 'LTC'), ('DOGE', 'DOGE'), ('DASH', 'DASH'), ('DGB', 'DGB'), ('ETH', 'ETH'), ('ATOM', 'ATOM'), ('BNB', 'BNB'), ('EOS', 'EOS'), ('FIO', 'FIO'), ('XRP', 'XRP')], max_length=100),
        ),
        migrations.AlterField(
            model_name='processedblock',
            name='network',
            field=models.CharField(choices=[('BTC', 'BTC'), ('BCH', 'BCH'), ('LTC', 'LTC'), ('DOGE', 'DOGE'), ('DASH', 'DASH'), ('DGB', 'DGB'), ('ETH', 'ETH'), ('ATOM', 'ATOM'), ('BNB', 'BNB'), ('EOS', 'EOS'), ('FIO', 'FIO'), ('XRP', 'XRP')], max_length=100),
        ),
    ]
