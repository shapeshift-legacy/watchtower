# Generated by Django 2.0.7 on 2019-02-10 21:22

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0015_transaction_is_erc20_fee'),
    ]

    operations = [
        migrations.AlterIndexTogether(
            name='processedblock',
            index_together={('network', 'block_height')},
        ),
    ]