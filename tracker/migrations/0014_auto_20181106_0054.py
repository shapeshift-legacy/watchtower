# Generated by Django 2.0.7 on 2018-11-06 07:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0013_auto_20180927_1009'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='block_hash',
            field=models.CharField(max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='block_height',
            field=models.IntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='block_time',
            field=models.DateTimeField(null=True),
        ),
    ]
