# Generated by Django 2.0.7 on 2018-08-27 19:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0006_auto_20180821_0255'),
    ]

    operations = [
        migrations.AlterField(
            model_name='address',
            name='address',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='xpub',
            name='xpub',
            field=models.CharField(max_length=255),
        ),
    ]
