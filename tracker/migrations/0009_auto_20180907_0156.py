# Generated by Django 2.0.7 on 2018-09-07 07:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0008_auto_20180828_0942'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='processedblock',
            unique_together={('network', 'block_hash')},
        ),
    ]
