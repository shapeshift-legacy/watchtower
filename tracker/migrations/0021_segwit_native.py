# Generated by Django 2.0.7 on 2019-05-25 21:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0020_auto_20190419_0948'),
    ]

    operations = [
        migrations.AlterField(
            model_name='xpub',
            name='script_type',
            field=models.CharField(choices=[('eth', 'eth'), ('p2pkh', 'p2pkh'), ('p2sh-p2wpkh', 'p2sh-p2wpkh'), ('p2wpkh', 'p2wpkh')], max_length=16),
        ),
    ]
