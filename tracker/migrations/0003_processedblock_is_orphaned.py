# Generated by Django 2.0.7 on 2018-08-15 16:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0002_processedblock'),
    ]

    operations = [
        migrations.AddField(
            model_name='processedblock',
            name='is_orphaned',
            field=models.BooleanField(default=False),
        ),
    ]
