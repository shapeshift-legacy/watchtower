# Generated by Django 2.0.7 on 2020-02-01 20:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0031_auto_20200201_1323'),
    ]

    operations = [
        
        migrations.RunSQL(
            """
                update tracker_erc20token
                set supported = true
                where lower(contract_address) in (
                lower('0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'));
            """
        )

    ]
